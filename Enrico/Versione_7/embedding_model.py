import ollama as ol
import numpy as np


class Embedder:
    def __init__(self, model_name: str = None, client: ol.AsyncClient = None):
        self.name = model_name

        if client is None:
            client = ol.AsyncClient("localhost")
        self.emb_cli = client

    def check_installation(self):
        installed_models = []
        error: bool = False

        for model in ol.list()['models']:
            installed_models.append(model['model'])

        if self.name not in installed_models:
            error = True
            print(f'{self.name} is not installed')

        if error:
            print(f'Installed models are:\n{installed_models}\n')

        return not error

    async def get_embedding(self, text: str) -> np.ndarray:
        """
        Create the embedding of the given text
        """
        response = await self.emb_cli.embeddings(model=self.name, prompt=text)
        return np.array(response['embedding'])

    @staticmethod
    def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        # FIXME: controllare che sia corretta
        return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))  # type: ignore
