import os
import json
import base64
import uuid
import time
import pika
import pandas as pd
import streamlit as st

from order_recognition.confs import config as conf

def make_email_hash_from_text(text: str) -> str:
    payload = {"fileContent": text}
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return base64.b64encode(base64.b64encode(raw)).decode("utf-8")


def rpc_call_to_worker(email_hash: str, timeout_seconds: int = 120) -> dict:
    rmq_url = conf.connection_url
    connection = pika.BlockingConnection(pika.URLParameters(rmq_url))
    channel = connection.channel()

    result = channel.queue_declare(queue="", exclusive=True)
    callback_queue = result.method.queue

    corr_id = str(uuid.uuid4())
    response_body: bytes | None = None

    def on_response(ch, method, props, body):
        nonlocal response_body
        if props.correlation_id == corr_id:
            response_body = body

    channel.basic_consume(queue=callback_queue, on_message_callback=on_response, auto_ack=True)

    message = {"email": email_hash}

    channel.basic_publish(
        exchange=conf.exchange,
        routing_key=conf.routing_key,
        properties=pika.BasicProperties(
            reply_to=callback_queue,
            correlation_id=corr_id,
            content_type="application/json",
        ),
        body=json.dumps(message, ensure_ascii=False).encode("utf-8"),
    )

    start = time.time()
    while response_body is None:
        connection.process_data_events(time_limit=1)
        if time.time() - start > timeout_seconds:
            channel.close()
            connection.close()
            raise TimeoutError("Timeout while waiting for worker response")

    channel.close()
    connection.close()

    try:
        return json.loads(response_body)
    except Exception:
        try:
            return json.loads(response_body.decode("utf-8"))
        except Exception:
            return {"raw": response_body.decode("utf-8", errors="replace")}


def main():
    st.title("Order Recognition: RabbitMQ Client")
    st.caption("Один запрос — один ответ. Сообщение отправляется в очередь get_message через exchange 'ai'.")

    @st.cache_data(show_spinner=False)
    def load_materials_map(csv_path: str = "order_recognition/data/mats_with_features.csv") -> dict:
        df = pd.read_csv(csv_path, dtype={"Материал": str, "Полное наименование материала": str})
        df["Материал"] = df["Материал"].astype(str)
        df["Полное наименование материала"] = df["Полное наименование материала"].astype(str)
        return dict(zip(df["Материал"], df["Полное наименование материала"]))

    material_id_to_name = load_materials_map()

    def material_name(material_id: str) -> str:
        if not material_id:
            return "—"
        return material_id_to_name.get(str(material_id), str(material_id))

    if "history" not in st.session_state:
        st.session_state.history = []  # list[{id, text, result, ts}]
    if "selected_history_id" not in st.session_state and st.session_state.history:
        st.session_state.selected_history_id = st.session_state.history[-1]["id"]

    with st.sidebar:
        st.header("История запросов")
        if st.button("Очистить историю"):
            st.session_state.history = []
            st.session_state.selected_history_id = None
        entries = [
            (h["id"], f"{i+1}. {h['text'][:30]}" if h.get("text") else f"{i+1}.")
            for i, h in enumerate(st.session_state.history)
        ]
        selected_label = None
        if entries:
            id_list, labels = zip(*entries)
            idx_default = id_list.index(st.session_state.get("selected_history_id", id_list[-1])) if st.session_state.get("selected_history_id") in id_list else 0
            selected_label = st.selectbox("Выберите запрос", labels, index=idx_default)
            # map label -> id
            label_to_id = {label: id_ for id_, label in entries}
            st.session_state.selected_history_id = label_to_id.get(selected_label)

    default_text = "швеллер 10п"
    text = st.text_area("Текст запроса", value=default_text, height=160)

    if st.button("Отправить в RabbitMQ"):
        try:
            email_hash = make_email_hash_from_text(text)
            with st.spinner("Отправка и ожидание ответа..."):
                result = rpc_call_to_worker(email_hash=email_hash)
            # Save to history
            hid = str(uuid.uuid4())
            st.session_state.history.append({"id": hid, "text": text, "result": result, "ts": time.time()})
            st.session_state.selected_history_id = hid
            st.success("Ответ получен")
        except TimeoutError as te:
            st.error(f"Таймаут ожидания ответа: {te}")
        except Exception as exc:
            st.error(f"Ошибка отправки/получения: {exc}")

    current_item = None
    if st.session_state.history:
        if st.session_state.get("selected_history_id"):
            for h in st.session_state.history:
                if h["id"] == st.session_state.selected_history_id:
                    current_item = h
                    break
        if current_item is None:
            current_item = st.session_state.history[-1]

    if current_item:
        result = current_item.get("result", {})
        positions = result.get("positions", []) if isinstance(result, dict) else []
        # If positions is a dict with numeric keys as strings, convert to list by key order
        if isinstance(positions, dict):
            try:
                positions = [positions[k] for k in sorted(positions.keys(), key=lambda x: int(x))]
            except Exception:
                positions = list(positions.values())

        st.subheader(f"Распознанные позиции ({len(positions)})")

        for idx, pos in enumerate(positions):
            req_text = pos.get("request_text", current_item.get("text", ""))
            st.markdown(f"**Запрос:** {req_text}")

            rows = []
            for i in range(1, 6):
                mid_key = f"material{i}_id"
                w_key = f"weight_{i}"
                mat_id = pos.get(mid_key)
                if not mat_id:
                    continue
                weight_val = pos.get(w_key)
                try:
                    weight_num = int(float(weight_val)) if weight_val is not None else None
                except Exception:
                    weight_num = None
                rows.append({"Материал": material_name(mat_id), "Вес": weight_num})

            if rows:
                df_view = pd.DataFrame(rows, columns=["Материал", "Вес"])
                st.table(df_view)
            else:
                st.info("Нет данных по материалам")

            with st.expander("Показать JSON"):
                st.json(pos)
            st.divider()


if __name__ == "__main__":
    main()


