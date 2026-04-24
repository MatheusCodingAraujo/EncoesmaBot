usuarios: dict[int, dict] = {}


def get_usuario(user_id: int) -> dict:
    if user_id not in usuarios:
        usuarios[user_id] = {
            "estado": "inicial",
            "produtos": [],
            "produto_atual": None,
            "categoria_atual": None,
            "tipo_ponto": None,
            "admin_func_id":  None,
            "admin_func_map": {},
        }
    return usuarios[user_id]
