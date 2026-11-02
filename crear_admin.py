from getpass import getpass
from database import get_connection
from security import hash_password, validar_fortaleza_password
from app import validation


def main():
    print("Crear o actualizar administrador de Foxy Lancer")
    nombre = input("Nombre del administrador: ").strip()
    correo = input("Correo del administrador: ").strip().lower()
    password = getpass("Contraseña (mínimo 8 caracteres, mayúscula, minúscula y número): ")
    confirmacion = getpass("Repite la contraseña: ")

    if not nombre or not correo:
        print("Nombre y correo son obligatorios.")
        return
    try:
        nombre = validation.validar_nombre(nombre)
        correo = validation.validar_email(correo)
        password = validar_fortaleza_password(password)
    except ValueError as exc:
        print("Error de validación:", exc)
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
                "INSERT INTO usuarios (nombre, correo, password_hash, rol, activo) VALUES (%s,%s,%s,'admin',1)",
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
