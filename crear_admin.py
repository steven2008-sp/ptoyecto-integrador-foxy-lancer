from getpass import getpass
from database import get_connection
from security import hash_password


def main():
    print("Crear o actualizar administrador de Foxy Lancer")
    nombre = input("Nombre del administrador: ").strip()
    correo = input("Correo del administrador: ").strip().lower()
    password = getpass("Contraseña (mínimo 8 caracteres): ")
    confirmacion = getpass("Repite la contraseña: ")

    if not nombre or not correo or "@" not in correo:
        print("Nombre o correo no válido.")
        return
    if len(password) < 8:
        print("La contraseña debe tener al menos 8 caracteres.")
        return
    if password != confirmacion:
        print("Las contraseñas no coinciden.")
        return

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT id FROM usuarios WHERE correo = %s", (correo,))
        existing = cursor.fetchone()
        hashed = hash_password(password)
        if existing:
            cursor.execute(
                "UPDATE usuarios SET nombre=%s, password_hash=%s, rol='admin', activo=1 WHERE id=%s",
                (nombre, hashed, existing[0])
            )
            print("Cuenta existente convertida en administrador.")
        else:
            cursor.execute(
                "INSERT INTO usuarios (nombre, correo, password_hash, rol) VALUES (%s,%s,%s,'admin')",
                (nombre, correo, hashed)
            )
            print("Administrador creado.")
        connection.commit()
    except Exception as exc:
        connection.rollback()
        print("No se pudo crear el administrador:", exc)
    finally:
        connection.close()


if __name__ == "__main__":
    main()
