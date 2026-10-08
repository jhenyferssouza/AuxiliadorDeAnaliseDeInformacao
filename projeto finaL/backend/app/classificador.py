"""Carrega e executa o classificador de claims.

Suporta os dois formatos de arquivo:
  * NOVO: dict salvo com joblib -> {'model': MultinomialNB, 'tfidf', 'scaler', 'feature_cols', 'text_col'}
  * ANTIGO: Pipeline do scikit-learn com `feature_names_in_`
Para trocar de modelo basta substituir o arquivo `modelo_pipeline_completo.pkl`.
"""
import joblib
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix, hstack


class Classificador:
    def __init__(self, caminho):
        obj = joblib.load(caminho)
        self.novo = isinstance(obj, dict)
        if self.novo:
            self.nb = obj["model"]
            self.tfidf = obj["tfidf"]
            self.scaler = obj["scaler"]
            self.colunas = list(obj["feature_cols"])
            self.classes = [c.item() if hasattr(c, "item") else c for c in self.nb.classes_]
        else:
            self.pipe = obj
            self.colunas = list(obj.feature_names_in_)
            self.classes = [c.item() if hasattr(c, "item") else c for c in obj.classes_]

    def proba(self, linhas: list[dict]) -> np.ndarray:
        """linhas = saída de analisar_texto(). Devolve matriz [n_sentenças, n_classes]."""
        df = pd.DataFrame(linhas)
        if not self.novo:
            return self.pipe.predict_proba(df[self.colunas])

        # o notebook novo chama a última feature de "e_pergunta"
        if "e_pergunta" not in df and "eh_pergunta" in df:
            df["e_pergunta"] = df["eh_pergunta"]
        numericas = self.scaler.transform(df[self.colunas])
        numericas = np.clip(numericas, 0, None)          # Naive Bayes não aceita negativos
        texto = self.tfidf.transform(df["sentenca"])      # frase já com pronomes resolvidos
        X = hstack([texto, csr_matrix(numericas)]).tocsr()  # ordem do treino: TF-IDF + numéricas
        return self.nb.predict_proba(X)
