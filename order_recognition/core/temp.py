import pandas as pd

df = pd.read_csv("order_recognition/data/mats.csv", index_col=0)

unik = df["Название иерархии-0"].unique()
print(unik, len(unik))
