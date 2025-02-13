import asyncio
import pathlib
from yandex_cloud_ml_sdk import AsyncYCloudML
from order_recognition.core.yandexgpt import custom_yandex_gpt
# from yandex_cloud_ml_sdk.auth import YandexCloudCLIAuth


def local_path(path: str) -> pathlib.Path:
    return pathlib.Path(__file__).parent / path


async def main():

    ygpt = custom_yandex_gpt()
    ygpt.update_token()
    sdk = AsyncYCloudML(
        folder_id=ygpt.headers["x-folder-id"],
        auth=ygpt.headers["Authorization"][7:],
    )

    # Создаем датасет для дообучения базовой модели YandexGPT Lite
    dataset_draft = sdk.datasets.draft_from_path(
        task_type="TextToTextGeneration",
        path="training/train_data/FT_lora_AG.json",
        upload_format="jsonlines",
        name="YandexGPT tuning",
    )

    # Дождемся окончания загрузки данных и создания датасета
    operation = await dataset_draft.upload_deferred()
    dataset = await operation
    print(f"new {dataset=}")


if __name__ == "__main__":
    asyncio.run(main())