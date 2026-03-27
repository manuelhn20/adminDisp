import re
import random
import logging
from datetime import datetime, timedelta
from werkzeug.security import check_password_hash, generate_password_hash
from flask import current_app
from ..core.db import get_db_empleados

logger = logging.getLogger('admin_disp.auth')


# ---------------------------------------------------------------------------
# Función auxiliar
# ---------------------------------------------------------------------------

def remap_estado_empleado(estado_valor):
    """Normaliza el campo estado de empleados a 1 (activo) o 0 (inactivo)."""
    if estado_valor in (1, '1', True, 'Active', 'active'):
        return 1
    if isinstance(estado_valor, str) and estado_valor.lower() in ('active', '1', 'true'):
        return 1
    return 0


# ---------------------------------------------------------------------------
# Servicio base
# ---------------------------------------------------------------------------

class AuthService:
    """Gestión de autenticación y usuarios desde empleados."""

    def __init__(self):
        self.conn = get_db_empleados()

    # ------------------------------------------------------------------
    # Autenticación
    # ------------------------------------------------------------------

    def verify_credentials(self, username, password):
        """Verifica credenciales contra la tabla usuarios."""
        try:
            logger.info("=== INICIO LOGIN: username='%s' ===", username)

            cur = self.conn.get_cursor()
            cur.execute(
                "SELECT id_usuario, password_hash, fk_id_empleado, fecha_ultimo_acceso, estado "
                "FROM usuarios WHERE username = ?",
                (username,)
            )
            user_row = cur.fetchone()
            if not user_row:
                logger.warning("Usuario no encontrado: '%s'", username)
                return False, None

            user_id, pwd_hash, empleado_id, fecha_ultimo_acceso, usuario_estado = user_row

            if usuario_estado in (0, '0', False):
                logger.warning("Usuario desactivado: '%s' (id=%s)", username, user_id)
                return False, None

            if pwd_hash is None:
                logger.warning("Usuario sin contraseña configurada: '%s'", username)
                return False, None

            if not password or not password.strip():
                logger.warning("Password vacío para usuario: '%s'", username)
                return False, None

            if len(password) < 8:
                logger.warning("Password demasiado corta para usuario: '%s'", username)
                return False, None

            if not check_password_hash(pwd_hash, password):
                logger.info("Password incorrecto para user='%s' (id=%s)", username, user_id)
                return False, None

            # Verificar empleado activo si corresponde
            if empleado_id:
                cur.execute("SELECT estado FROM empleados WHERE id_empleado = ?", (empleado_id,))
                emp_row = cur.fetchone()
                if emp_row:
                    estado_val = emp_row[0]
                    es_activo = estado_val in (1, None, 'Active', 'active') or (
                        isinstance(estado_val, str) and estado_val.lower() in ('active', '1')
                    )
                    if not es_activo:
                        logger.warning("Empleado inactivo: id=%s, estado=%s", empleado_id, estado_val)
                        return False, None

            cur.execute("UPDATE usuarios SET fecha_ultimo_acceso = GETDATE() WHERE id_usuario = ?", (user_id,))
            self.conn.commit()

            logger.info("LOGIN EXITOSO: user='%s', id=%s", username, user_id)
            return True, (user_id, username)

        except Exception:
            logger.exception("Error en verify_credentials para '%s'", username)
            return False, None

    # ------------------------------------------------------------------
    # Roles y empleados
    # ------------------------------------------------------------------

    def get_user_roles(self, user_id):
        """Obtiene roles de usuario (tabla legacy)."""
        try:
            cur = self.conn.get_cursor()
            cur.execute(
                "SELECT r.nombre_rol FROM usuarios_x_roles uxr "
                "JOIN roles r ON r.id_rol = uxr.fk_id_rol "
                "WHERE uxr.fk_id_usuario = ? ORDER BY r.nombre_rol",
                (user_id,)
            )
            return [r[0] for r in cur.fetchall()]
        except Exception:
            logger.error("Error obteniendo roles para user_id=%s", user_id)
            return []

    def get_empleado_name(self, user_id):
        """Obtiene nombre del empleado asociado al usuario."""
        try:
            cur = self.conn.get_cursor()
            cur.execute(
                "SELECT e.nombre_completo FROM usuarios u "
                "LEFT JOIN empleados e ON e.id_empleado = u.fk_id_empleado "
                "WHERE u.id_usuario = ?",
                (user_id,)
            )
            row = cur.fetchone()
            return row[0] if row and row[0] else None
        except Exception:
            logger.error("Error obteniendo nombre empleado para user_id=%s", user_id)
            return None

    def get_empleado_sucursal(self, user_id):
        """Obtiene la sucursal del empleado asociado al usuario (para operadores)."""
        try:
            cur = self.conn.get_cursor()
            cur.execute(
                "SELECT e.sucursal FROM usuarios u "
                "LEFT JOIN empleados e ON e.id_empleado = u.fk_id_empleado "
                "WHERE u.id_usuario = ?",
                (user_id,)
            )
            row = cur.fetchone()
            return row[0] if row and row[0] else None
        except Exception:
            logger.error("Error obteniendo sucursal empleado para user_id=%s", user_id)
            return None

    def get_all_employees(self):
        """Obtiene todos los empleados."""
        try:
            cur = self.conn.get_cursor()
            cur.execute(
                "SELECT id_empleado, nombre_completo, empresa, puesto, departamento "
                "FROM empleados ORDER BY nombre_completo"
            )
            return [
                {'IdEmpleado': r[0], 'NombreCompleto': r[1], 'Empresa': r[2], 'Cargo': r[3], 'Area': r[4]}
                for r in cur.fetchall()
            ]
        except Exception:
            logger.error("Error obteniendo empleados")
            return []

    def get_employees_without_user(self):
        """Obtiene empleados que no tienen usuario asignado."""
        try:
            cur = self.conn.get_cursor()
            cur.execute(
                "SELECT e.id_empleado, e.nombre_completo, e.empresa, e.puesto, e.departamento "
                "FROM empleados e "
                "WHERE e.id_empleado NOT IN "
                "  (SELECT fk_id_empleado FROM usuarios WHERE fk_id_empleado IS NOT NULL) "
                "ORDER BY e.nombre_completo"
            )
            return [
                {'IdEmpleado': r[0], 'NombreCompleto': r[1], 'Empresa': r[2], 'Cargo': r[3], 'Area': r[4]}
                for r in cur.fetchall()
            ]
        except Exception:
            logger.error("Error obteniendo empleados sin usuario")
            return []

    # ------------------------------------------------------------------
    # Gestión de usuarios (legacy)
    # ------------------------------------------------------------------

    def is_first_user_exists(self):
        """Verifica si existe algún usuario en el sistema."""
        try:
            cur = self.conn.get_cursor()
            cur.execute("SELECT COUNT(*) FROM usuarios")
            return cur.fetchone()[0] > 0
        except Exception:
            logger.error("Error verificando usuarios")
            return False

    def create_first_admin_usuario(self, username, password):
        """Crea el primer usuario admin (solo si no existe usuario previo)."""
        if self.is_first_user_exists():
            return False, "Ya existe un administrador en el sistema."
        try:
            cur = self.conn.get_cursor()
            self.conn.autocommit = False
            pwd_hash = generate_password_hash(password)
            cur.execute(
                "INSERT INTO usuarios (username, password_hash, fecha_creacion) VALUES (?, ?, GETDATE())",
                (username, pwd_hash)
            )
            cur.execute("SELECT @@IDENTITY")
            user_id = int(cur.fetchone()[0])
            cur.execute("SELECT TOP 1 id_rol FROM roles WHERE nombre_rol = 'admin'")
            admin_role = cur.fetchone()
            if admin_role:
                cur.execute(
                    "INSERT INTO usuarios_x_roles (fk_id_usuario, fk_id_rol, fecha_asignacion) VALUES (?, ?, GETDATE())",
                    (user_id, admin_role[0])
                )
            self.conn.commit()
            logger.info("Primer admin creado: %s", username)
            return True, user_id
        except Exception:
            self.conn.rollback()
            logger.exception("Error creando primer admin")
            return False, "Error al crear administrador"
        finally:
            self.conn.autocommit = True

    def create_user(self, username, password, role_name, employee_id=None):
        """Crea un usuario con hash de contraseña y rol asignado."""
        if not username or len(username) < 3:
            return False, "El nombre de usuario debe tener al menos 3 caracteres"
        if not password or len(password) < 6:
            return False, "La contraseña debe tener al menos 6 caracteres"
        if not role_name:
            return False, "Debe especificar un rol"

        try:
            cur = self.conn.get_cursor()
            self.conn.autocommit = False

            cur.execute("SELECT COUNT(*) FROM usuarios WHERE username = ?", (username,))
            if cur.fetchone()[0] > 0:
                self.conn.rollback()
                return False, f"El usuario '{username}' ya existe"

            cur.execute("SELECT id_rol FROM roles WHERE nombre_rol = ?", (role_name,))
            role_row = cur.fetchone()
            if not role_row:
                self.conn.rollback()
                return False, f"El rol '{role_name}' no existe"
            role_id = role_row[0]

            if employee_id:
                try:
                    employee_id = int(employee_id)
                    cur.execute("SELECT COUNT(*) FROM empleados WHERE id_empleado = ?", (employee_id,))
                    if cur.fetchone()[0] == 0:
                        self.conn.rollback()
                        return False, f"El empleado con ID {employee_id} no existe"
                except (ValueError, TypeError):
                    self.conn.rollback()
                    return False, "ID de empleado inválido"

            pwd_hash = generate_password_hash(password)
            cur.execute(
                "INSERT INTO usuarios (username, password_hash, fk_id_empleado, fecha_creacion) "
                "VALUES (?, ?, ?, GETDATE())",
                (username, pwd_hash, employee_id)
            )
            cur.execute("SELECT @@IDENTITY")
            user_id = int(cur.fetchone()[0])
            cur.execute(
                "INSERT INTO usuarios_x_roles (fk_id_usuario, fk_id_rol, fecha_asignacion) VALUES (?, ?, GETDATE())",
                (user_id, role_id)
            )
            self.conn.commit()
            logger.info("Usuario creado: %s (ID: %s, Rol: %s)", username, user_id, role_name)
            return True, user_id

        except Exception:
            self.conn.rollback()
            logger.exception("Error creando usuario")
            return False, "Error al crear usuario"
        finally:
            self.conn.autocommit = True

    def list_all_users(self):
        """Lista todos los usuarios con sus roles."""
        try:
            cur = self.conn.get_cursor()
            cur.execute(
                "SELECT u.id_usuario, u.username, u.fk_id_empleado, "
                "STRING_AGG(r.nombre_rol, ', ') as roles "
                "FROM usuarios u "
                "LEFT JOIN usuarios_x_roles ur ON ur.fk_id_usuario = u.id_usuario "
                "LEFT JOIN roles r ON r.id_rol = ur.fk_id_rol "
                "GROUP BY u.id_usuario, u.username, u.fk_id_empleado ORDER BY u.username"
            )
            rows = cur.fetchall()
            cur.execute("SELECT id_empleado, nombre_completo FROM empleados WHERE id_empleado IS NOT NULL")
            emp_map = {row[0]: row[1] for row in cur.fetchall()}
            return [
                {
                    'IdUsuario': u_id,
                    'Usuario': username,
                    'IdEmpleado': emp_id,
                    'NombreCompleto': emp_map.get(emp_id, '') if emp_id else '',
                    'Roles': roles or '',
                }
                for u_id, username, emp_id, roles in rows
            ]
        except Exception:
            logger.error("Error listando usuarios")
            return []

    def get_user_by_id(self, user_id):
        """Obtiene detalles de un usuario por ID."""
        try:
            cur = self.conn.get_cursor()
            cur.execute(
                "SELECT u.id_usuario, u.username, u.fk_id_empleado, "
                "(SELECT TOP 1 id_rol FROM usuarios_x_roles WHERE fk_id_usuario = u.id_usuario) "
                "FROM usuarios u WHERE u.id_usuario = ?",
                (user_id,)
            )
            row = cur.fetchone()
            if not row:
                return None
            emp_name = ''
            if row[2]:
                cur.execute("SELECT nombre_completo FROM empleados WHERE id_empleado = ?", (row[2],))
                emp_row = cur.fetchone()
                emp_name = emp_row[0] if emp_row else ''
            return {'IdUsuario': row[0], 'Usuario': row[1], 'IdEmpleado': row[2], 'NombreCompleto': emp_name, 'IdRol': row[3]}
        except Exception:
            logger.error("Error obteniendo usuario %s", user_id)
            return None

    def update_user(self, user_id, role_id, password=None):
        """Actualiza rol y/o contraseña de un usuario."""
        try:
            cur = self.conn.get_cursor()
            self.conn.autocommit = False
            cur.execute("DELETE FROM usuarios_x_roles WHERE fk_id_usuario = ?", (user_id,))
            cur.execute(
                "INSERT INTO usuarios_x_roles (fk_id_usuario, fk_id_rol) VALUES (?, ?)",
                (user_id, role_id)
            )
            if password:
                cur.execute(
                    "UPDATE usuarios SET password_hash = ? WHERE id_usuario = ?",
                    (generate_password_hash(password), user_id)
                )
            self.conn.commit()
            return True, None
        except Exception:
            self.conn.rollback()
            logger.exception("Error actualizando usuario %s", user_id)
            return False, "Error al actualizar usuario"
        finally:
            self.conn.autocommit = True

    def deactivate_user(self, user_id):
        """Desactiva un usuario removiendo sus roles."""
        try:
            cur = self.conn.get_cursor()
            cur.execute("DELETE FROM usuarios_x_roles WHERE fk_id_usuario = ?", (user_id,))
            self.conn.commit()
            return True, None
        except Exception:
            self.conn.rollback()
            logger.exception("Error desactivando usuario %s", user_id)
            return False, "Error al desactivar usuario"

    def list_deactivated_users(self):
        """Lista usuarios sin roles (desactivados)."""
        try:
            cur = self.conn.get_cursor()
            cur.execute(
                "SELECT u.id_usuario, u.username, u.fk_id_empleado FROM usuarios u "
                "WHERE u.id_usuario NOT IN (SELECT fk_id_usuario FROM usuarios_x_roles) "
                "ORDER BY u.username"
            )
            rows = cur.fetchall()
            cur.execute("SELECT id_empleado, nombre_completo FROM empleados WHERE id_empleado IS NOT NULL")
            emp_map = {row[0]: row[1] for row in cur.fetchall()}
            return [
                {'IdUsuario': u_id, 'Usuario': username, 'IdEmpleado': emp_id,
                 'NombreCompleto': emp_map.get(emp_id, '') if emp_id else ''}
                for u_id, username, emp_id in rows
            ]
        except Exception:
            logger.error("Error listando usuarios desactivados")
            return []

    def get_roles(self):
        """Obtiene lista de roles disponibles."""
        try:
            cur = self.conn.get_cursor()
            cur.execute("SELECT id_rol, nombre_rol FROM roles ORDER BY nombre_rol")
            return [{'id_rol': r[0], 'nombre_rol': r[1]} for r in cur.fetchall()]
        except Exception:
            logger.error("Error obteniendo roles")
            return []

    def restore_user(self, user_id):
        """Reactiva un usuario asignándole el rol 'operador' por defecto."""
        try:
            cur = self.conn.get_cursor()
            self.conn.autocommit = False
            cur.execute("SELECT TOP 1 id_rol FROM roles WHERE nombre_rol = 'operador'")
            default_role = cur.fetchone()
            if not default_role:
                cur.execute("SELECT TOP 1 id_rol FROM roles")
                default_role = cur.fetchone()
            if not default_role:
                self.conn.rollback()
                return False, "No hay roles disponibles en el sistema"
            cur.execute(
                "INSERT INTO usuarios_x_roles (fk_id_usuario, fk_id_rol, fecha_asignacion) VALUES (?, ?, GETDATE())",
                (user_id, default_role[0])
            )
            self.conn.commit()
            logger.info("Usuario %s restaurado con rol por defecto", user_id)
            return True, None
        except Exception:
            self.conn.rollback()
            logger.exception("Error restaurando usuario %s", user_id)
            return False, "Error al restaurar usuario"
        finally:
            self.conn.autocommit = True

    def set_user_estado(self, user_id, estado):
        """Establece el estado del usuario y gestiona roles según corresponda."""
        cur = None
        try:
            cur = self.conn.get_cursor()
            self.conn.autocommit = False
            messages = []
            affected = 0

            if int(estado) == 0:
                # Eliminar roles
                for sql in (
                    "DELETE FROM empleados.dbo.usuarios_x_roles_x_sistemas WHERE fk_id_usuario = ?",
                    "DELETE FROM usuarios_x_roles WHERE fk_id_usuario = ?",
                ):
                    try:
                        cur.execute(sql, (user_id,))
                        messages.append(f"DELETE roles '{sql.split()[2]}' rc={cur.rowcount}")
                    except Exception as exc:
                        logger.exception("Error borrando roles '%s': %s", sql, exc)

                # Limpiar credenciales y marcar inactivo
                for sql in (
                    "UPDATE empleados.dbo.usuarios SET password_hash=NULL, codigo=NULL, "
                    "fecha_codigo=NULL, codigo_intentos_fallidos=0, estado=0 WHERE id_usuario=?",
                    "UPDATE usuarios SET password_hash=NULL, codigo=NULL, "
                    "fecha_codigo=NULL, codigo_intentos_fallidos=0, estado=0 WHERE id_usuario=?",
                ):
                    try:
                        cur.execute(sql, (user_id,))
                        rc = cur.rowcount or 0
                        affected += rc
                        messages.append(f"UPDATE inactivo rc={rc}")
                        if rc > 0:
                            break
                    except Exception as exc:
                        logger.exception("Error actualizando estado 0: %s", exc)
            else:
                for sql in (
                    "UPDATE empleados.dbo.usuarios SET estado=1 WHERE id_usuario=?",
                    "UPDATE usuarios SET estado=1 WHERE id_usuario=?",
                ):
                    try:
                        cur.execute(sql, (user_id,))
                        rc = cur.rowcount or 0
                        affected += rc
                        messages.append(f"UPDATE activo rc={rc}")
                        if rc > 0:
                            break
                    except Exception as exc:
                        logger.exception("Error actualizando estado 1: %s", exc)

            self.conn.commit()
            summary = "; ".join(messages) or "No statements executed"
            logger.info("set_user_estado user_id=%s estado=%s affected=%s | %s", user_id, estado, affected, summary)
            return True, summary

        except Exception:
            try:
                self.conn.rollback()
            except Exception:
                pass
            logger.exception("Error seteando estado usuario %s", user_id)
            return False, "Error al actualizar estado"
        finally:
            try:
                self.conn.autocommit = True
            except Exception:
                pass

    def sync_users_with_empleados_estado(self):
        """Sincroniza usuarios.estado según empleados.estado."""
        updated = 0
        try:
            cur = self.conn.get_cursor()
            cur.execute(
                "SELECT id_usuario, fk_id_empleado FROM empleados.dbo.usuarios "
                "WHERE fk_id_empleado IS NOT NULL"
            )
            rows = cur.fetchall()
            for uid, emp_id in rows:
                try:
                    cur.execute(
                        "SELECT estado FROM empleados.dbo.empleados WHERE id_empleado = ?", (emp_id,)
                    )
                    r = cur.fetchone()
                    if not r:
                        continue
                    emp_estado = remap_estado_empleado(r[0])
                    cur.execute(
                        "SELECT estado FROM empleados.dbo.usuarios WHERE id_usuario = ?", (uid,)
                    )
                    cur_row = cur.fetchone()
                    if cur_row and cur_row[0] != emp_estado:
                        cur.execute(
                            "UPDATE empleados.dbo.usuarios SET estado=? WHERE id_usuario=?",
                            (emp_estado, uid)
                        )
                        updated += 1
                except Exception:
                    continue
            self.conn.commit()
        except Exception:
            try:
                self.conn.rollback()
            except Exception:
                pass
            logger.exception("Error sincronizando usuarios con empleados")
        return updated


# ---------------------------------------------------------------------------
# Servicio extendido (sistema multi-roles)
# ---------------------------------------------------------------------------

class AuthServiceExtended(AuthService):
    """Extensión de AuthService para el sistema de roles por sistema."""

    # Mapeos compartidos
    _SISTEMA_KEYS = {
        'Administración de Dispositivos': 'dispositivos',
        'KARDEX': 'kardex',
        'Cuentas por Cobrar': 'cxc',
    }
    _SISTEMAS_MAP = {'dispositivos': 1, 'kardex': 2, 'cxc': 3}
    _ROLES_MAP = {'admin': 1, 'operador': 2, 'auditor': 3}

    def _empty_sistemas_roles(self):
        return {'dispositivos': None, 'kardex': None, 'cxc': None, 'is_super_admin': False}

    def _get_user_contact(self, user_id):
        """
        Devuelve (nombre_completo, username, email) del usuario.
        El email se obtiene del campo 'usuario' en la tabla empleados (contiene el correo corporativo).
        Retorna (None, None, None) si no se puede obtener.
        """
        try:
            cur = self.conn.get_cursor()
            cur.execute(
                "SELECT u.username, e.nombre_completo, e.usuario "
                "FROM empleados.dbo.usuarios u "
                "INNER JOIN empleados.dbo.empleados e ON e.id_empleado = u.fk_id_empleado "
                "WHERE u.id_usuario = ?",
                (user_id,)
            )
            row = cur.fetchone()
            if not row:
                return None, None, None
            username, nombre, email = row
            # Validar que sea un email corporativo
            if email and '@' in str(email):
                return nombre or username, username, email
            return nombre or username, username, None
        except Exception:
            logger.exception("Error obteniendo contacto del usuario %s", user_id)
            return None, None, None

    def get_user_systems_roles(self, user_id):
        """Obtiene los roles del usuario organizados por sistema."""
        try:
            cur = self.conn.get_cursor()
            cur.execute(
                "SELECT s.nombre_sistema, r.nombre_rol "
                "FROM empleados.dbo.usuarios_x_roles_x_sistemas uxrxs "
                "INNER JOIN empleados.dbo.sistemas s ON s.id_sistema = uxrxs.fk_id_sistema "
                "INNER JOIN empleados.dbo.roles r ON r.id_rol = uxrxs.fk_id_rol "
                "WHERE uxrxs.fk_id_usuario = ? AND uxrxs.activo = 1 AND s.activo = 1",
                (user_id,)
            )
            rows = cur.fetchall()
            cur.close()

            result = self._empty_sistemas_roles()
            for nombre_sistema, nombre_rol in rows:
                key = self._SISTEMA_KEYS.get(nombre_sistema)
                if key:
                    result[key] = nombre_rol

            result['is_super_admin'] = (
                result['dispositivos'] == 'admin' and
                result['kardex'] == 'admin' and
                result['cxc'] == 'admin'
            )
            return result

        except Exception:
            logger.exception('Error en get_user_systems_roles para user_id=%s', user_id)
            return self._empty_sistemas_roles()

    def is_super_admin(self, user_id):
        return self.get_user_systems_roles(user_id).get('is_super_admin', False)

    def get_active_employees_with_email(self):
        """Obtiene empleados activos con email válido."""
        try:
            cur = self.conn.get_cursor()
            cur.execute(
                "SELECT id_empleado, nombre_completo, usuario, estado "
                "FROM empleados.dbo.empleados "
                "WHERE estado='Active' AND usuario IS NOT NULL AND usuario != '' AND usuario LIKE '%@%' "
                "ORDER BY nombre_completo"
            )
            rows = cur.fetchall()
            cur.close()
            return [{'id_empleado': r[0], 'nombre_completo': r[1], 'usuario': r[2], 'estado': r[3]} for r in rows]
        except Exception:
            logger.exception("Error obteniendo empleados activos con email")
            return []

    def get_all_active_employees(self):
        """Obtiene todos los empleados activos (con o sin usuario)."""
        try:
            cur = self.conn.get_cursor()
            cur.execute(
                "SELECT id_empleado, nombre_completo, usuario, estado, "
                "CASE WHEN usuario IS NOT NULL AND usuario != '' AND usuario LIKE '%@%' THEN 1 ELSE 0 END AS tiene_usuario "
                "FROM empleados.dbo.empleados WHERE estado='Active' "
                "ORDER BY CASE WHEN usuario IS NOT NULL AND usuario != '' AND usuario LIKE '%@%' THEN 0 ELSE 1 END, "
                "nombre_completo"
            )
            rows = cur.fetchall()
            cur.close()
            return [
                {'id_empleado': r[0], 'nombre_completo': r[1], 'usuario': r[2] or None,
                 'estado': r[3], 'tiene_usuario': bool(r[4])}
                for r in rows
            ]
        except Exception:
            logger.exception("Error obteniendo todos los empleados activos")
            return []

    def get_sistemas(self):
        """Obtiene la lista de sistemas disponibles."""
        try:
            cur = self.conn.get_cursor()
            cur.execute(
                "SELECT id_sistema, nombre_sistema, descripcion, activo "
                "FROM empleados.dbo.sistemas WHERE activo=1 ORDER BY id_sistema"
            )
            result = [
                {
                    'id_sistema': r[0],
                    'nombre_sistema': r[1],
                    'nombre_lower': self._SISTEMA_KEYS.get(r[1], r[1].lower()),
                    'descripcion': r[2],
                    'activo': r[3],
                }
                for r in cur.fetchall()
            ]
            cur.close()
            return result
        except Exception:
            logger.exception("Error obteniendo sistemas")
            return []

    def get_roles_genericos(self):
        """Obtiene roles genéricos (admin, operador, auditor; excluye superAdmin)."""
        try:
            cur = self.conn.get_cursor()
            cur.execute(
                "SELECT id_rol, nombre_rol, descripcion "
                "FROM empleados.dbo.roles WHERE id_rol IN (1,2,3) ORDER BY id_rol"
            )
            result = [{'id_rol': r[0], 'nombre_rol': r[1], 'descripcion': r[2]} for r in cur.fetchall()]
            cur.close()
            return result
        except Exception:
            logger.exception("Error obteniendo roles genéricos")
            return []

    def get_all_users(self):
        """Obtiene todos los usuarios del sistema."""
        try:
            cur = self.conn.get_cursor()
            cur.execute(
                "SELECT u.id_usuario, u.username, e.nombre_completo, u.fecha_creacion "
                "FROM empleados.dbo.usuarios u "
                "LEFT JOIN empleados.dbo.empleados e ON e.id_empleado = u.fk_id_empleado "
                "ORDER BY u.id_usuario"
            )
            result = [
                {
                    'id_usuario': r[0],
                    'username': r[1],
                    'empleado_nombre': r[2] or 'Sin empleado',
                    'fecha_creacion': r[3].isoformat() if r[3] else None,
                }
                for r in cur.fetchall()
            ]
            cur.close()
            return result
        except Exception:
            logger.exception("Error obteniendo usuarios")
            return []

    def get_usuario_by_id(self, user_id):
        """Obtiene detalles completos de un usuario."""
        try:
            cur = self.conn.get_cursor()
            cur.execute(
                "SELECT u.id_usuario, u.username, u.password_hash, u.fecha_ultimo_acceso, "
                "u.fecha_creacion, u.codigo, u.fecha_codigo, u.codigo_intentos_fallidos, "
                "u.codigo_regenerado, u.estado, e.nombre_completo "
                "FROM empleados.dbo.usuarios u "
                "LEFT JOIN empleados.dbo.empleados e ON e.id_empleado = u.fk_id_empleado "
                "WHERE u.id_usuario = ?",
                (user_id,)
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                'id_usuario': row[0],
                'username': row[1],
                'password_hash': row[2],
                'fecha_ultimo_acceso': row[3].isoformat() if row[3] else None,
                'fecha_creacion': row[4].isoformat() if row[4] else None,
                'codigo': row[5],
                'fecha_codigo': row[6].isoformat() if row[6] else None,
                'codigo_intentos_fallidos': row[7],
                'codigo_regenerado': row[8],
                'estado': row[9],
                'empleado_nombre': row[10] or 'Sin empleado',
            }
        except Exception:
            logger.exception("Error obteniendo usuario %s", user_id)
            return None

    def create_user_with_systems(self, username, password, employee_id, sistemas_roles):
        """Crea un usuario base (sin password ni roles; se asignan con update_user_systems_roles)."""
        if not username or len(username) < 3:
            return False, "El nombre de usuario debe tener al menos 3 caracteres"
        if not employee_id:
            return False, "Debe seleccionar un empleado"
        try:
            cur = self.conn.get_cursor()
            self.conn.autocommit = False

            cur.execute(
                "SELECT COUNT(*) FROM empleados.dbo.usuarios WHERE username = ?", (username,)
            )
            if cur.fetchone()[0] > 0:
                self.conn.rollback()
                return False, f"El usuario '{username}' ya existe"

            cur.execute(
                "SELECT estado FROM empleados.dbo.empleados WHERE id_empleado = ?", (employee_id,)
            )
            emp_row = cur.fetchone()
            if not emp_row:
                self.conn.rollback()
                return False, "Empleado no encontrado"
            if remap_estado_empleado(emp_row[0]) != 1:
                self.conn.rollback()
                return False, "El empleado no está activo"

            cur.execute(
                "INSERT INTO empleados.dbo.usuarios (username, password_hash, fk_id_empleado, fecha_creacion) "
                "VALUES (?, NULL, ?, GETDATE())",
                (username, employee_id)
            )
            cur.execute("SELECT @@IDENTITY")
            user_id = int(cur.fetchone()[0])
            self.conn.commit()
            logger.info("Usuario base creado: %s (id=%s)", username, user_id)
            return True, {'user_id': user_id}

        except Exception:
            self.conn.rollback()
            logger.exception("Error creando usuario")
            return False, "Error al crear usuario"
        finally:
            self.conn.autocommit = True

    def update_user_systems_roles(self, user_id, sistemas_roles, usuario_actual='UNKNOWN', db_main=None):
        """Actualiza roles por sistema y genera código temporal si es el primer acceso.
        
        Args:
            user_id: ID del usuario a actualizar
            sistemas_roles: Dict con roles por sistema
            usuario_actual: Username de quien hace el cambio (para auditoría)
            db_main: Parámetro ignorado (mantenido por compatibilidad), usa self.conn para auditoría
        """
        try:
            cur = self.conn.get_cursor()
            self.conn.autocommit = False

            # Obtener datos actuales del usuario
            cur.execute(
                "SELECT username, fecha_ultimo_acceso, codigo, password_hash "
                "FROM empleados.dbo.usuarios WHERE id_usuario = ?",
                (user_id,)
            )
            user_row = cur.fetchone()
            if not user_row:
                self.conn.rollback()
                return False, "Usuario no encontrado"

            username_target, fecha_ultimo_acceso, codigo_actual, password_hash = user_row
            
            # Obtener roles actuales para comparación en auditoría
            cur.execute(
                "SELECT s.nombre_sistema, r.nombre_rol "
                "FROM empleados.dbo.usuarios_x_roles_x_sistemas uxrxs "
                "LEFT JOIN empleados.dbo.sistemas s ON s.id_sistema = uxrxs.fk_id_sistema "
                "LEFT JOIN empleados.dbo.roles r ON r.id_rol = uxrxs.fk_id_rol "
                "WHERE uxrxs.fk_id_usuario = ? AND uxrxs.activo = 1",
                (user_id,)
            )
            roles_anteriores = {row[0]: row[1] for row in cur.fetchall() if row[0] is not None}
            
            tiene_algun_rol = any(sistemas_roles.values())

            debe_generar_codigo = (
                tiene_algun_rol and
                fecha_ultimo_acceso is None and
                codigo_actual is None and
                password_hash is None
            )

            # Reemplazar asignaciones de roles
            cur.execute(
                "DELETE FROM empleados.dbo.usuarios_x_roles_x_sistemas WHERE fk_id_usuario = ?",
                (user_id,)
            )
            for sistema_key, rol_nombre in sistemas_roles.items():
                if rol_nombre and sistema_key in self._SISTEMAS_MAP:
                    rol_id = self._ROLES_MAP.get(rol_nombre)
                    if rol_id:
                        cur.execute(
                            "INSERT INTO empleados.dbo.usuarios_x_roles_x_sistemas "
                            "(fk_id_usuario, fk_id_sistema, fk_id_rol, fecha_asignacion, activo) "
                            "VALUES (?, ?, ?, GETDATE(), 1)",
                            (user_id, self._SISTEMAS_MAP[sistema_key], rol_id)
                        )

            # Actualizar estado del usuario según si tiene roles activos
            cur.execute(
                "SELECT COUNT(*) FROM empleados.dbo.usuarios_x_roles_x_sistemas "
                "WHERE fk_id_usuario = ? AND activo = 1",
                (user_id,)
            )
            row_cnt = cur.fetchone()
            cuenta_roles = int(row_cnt[0]) if row_cnt and row_cnt[0] is not None else 0
            nuevo_estado = 1 if cuenta_roles > 0 else 0
            try:
                cur.execute(
                    "UPDATE empleados.dbo.usuarios SET estado=? WHERE id_usuario=?",
                    (nuevo_estado, user_id)
                )
            except Exception:
                pass  # Ignorar si la columna no existe en entornos legacy

            # Generar código temporal si aplica
            codigo_generado = None
            if debe_generar_codigo:
                codigo_generado = ''.join(str(random.randint(0, 9)) for _ in range(6))
                cur.execute(
                    "UPDATE empleados.dbo.usuarios "
                    "SET codigo=?, fecha_codigo=GETDATE(), codigo_intentos_fallidos=0, codigo_regenerado=0 "
                    "WHERE id_usuario=?",
                    (codigo_generado, user_id)
                )
                logger.info("Código temporal generado para usuario %s", user_id)

            self.conn.commit()
            logger.info("Roles actualizados para usuario %s por %s", user_id, usuario_actual)

            # Registrar en auditoría (misma BD empleados)
            try:
                # Construir strings de roles en formato: sistema: rol; sistema: rol
                rol_anterior_str = self._format_roles_string(roles_anteriores)
                nuevos_roles = {sis: rol for sis, rol in sistemas_roles.items() if rol}
                rol_nuevo_str = self._format_roles_string(nuevos_roles)
                
                self._log_auditoria_cambio_roles(
                    usuario_actual, 
                    username_target,
                    user_id,
                    rol_anterior_str,
                    rol_nuevo_str
                )
            except Exception as e:
                logger.warning("Error registrando auditoría de cambio de roles: %s", str(e))

            # Nota: El envío de emails fue removido. Los códigos se generan pero no se notifican por email.

            mensaje = "Roles actualizados correctamente"
            if codigo_generado:
                mensaje += ". Se ha generado un código temporal de acceso."
            return True, mensaje

        except Exception:
            self.conn.rollback()
            logger.exception("Error actualizando roles usuario %s", user_id)
            return False, "Error al actualizar roles"
        finally:
            self.conn.autocommit = True

    def _format_roles_string(self, roles_dict):
        """Formatea roles en orden específico: adminDisp, cxc, kardex
        
        Formato: 'adminDisp: admin; cxc: operador; kardex: auditor'
        Si no hay roles, retorna string vacío.
        """
        if not roles_dict:
            return ""
        
        # Aceptar llaves largas (desde DB) y llaves cortas (payload frontend).
        sistema_display = {
            'Administración de Dispositivos': 'adminDisp',
            'dispositivos': 'adminDisp',
            'Cuentas por Cobrar': 'cxc',
            'cxc': 'cxc',
            'KARDEX': 'kardex',
            'kardex': 'kardex',
        }

        # Orden de salida requerido por auditoría.
        orden_display = ['adminDisp', 'cxc', 'kardex']
        normalizado = {}
        for sistema_key, rol in roles_dict.items():
            if not rol:
                continue
            display_name = sistema_display.get(sistema_key)
            if display_name:
                normalizado[display_name] = rol

        parts = []
        for display_name in orden_display:
            rol = normalizado.get(display_name)
            if rol:
                parts.append(f"{display_name}: {rol}")
        
        return "; ".join(parts) if parts else ""

    def _log_auditoria_cambio_roles(self, usuario_realiza, usuario_afectado, id_usuario_afectado, rol_anterior, rol_nuevo):
        """Registra cambio de roles en tabla auditoria de BD empleados (misma conexión)."""
        try:
            cur = self.conn.get_cursor()
            cur.execute(
                "INSERT INTO empleados.dbo.auditoria "
                "(usuario_que_realiza, usuario_afectado, id_usuario_afectado, rolAnterior, rolNuevo) "
                "VALUES (?, ?, ?, ?, ?)",
                (usuario_realiza, usuario_afectado, id_usuario_afectado, rol_anterior, rol_nuevo)
            )
            self.conn.commit()
            logger.info("Auditoría registrada: usuario=%s realizó cambio en usuario=%s", usuario_realiza, usuario_afectado)
        except Exception as e:
            logger.warning("Error en auditoría de roles: %s", str(e))

    def get_codigo_temporal(self, user_id):
        """Obtiene el código temporal de un usuario y verifica su vigencia."""
        try:
            cur = self.conn.get_cursor()
            cur.execute(
                "SELECT codigo, fecha_codigo, codigo_regenerado "
                "FROM empleados.dbo.usuarios WHERE id_usuario = ?",
                (user_id,)
            )
            row = cur.fetchone()
            if not row:
                return False, "Usuario no encontrado"
            codigo_db, fecha_gen, codigo_reg = row
            if not codigo_db:
                return False, "El usuario no tiene código temporal asignado"
            vigente = True
            if fecha_gen and datetime.now() > fecha_gen + timedelta(hours=1):
                vigente = False
            return True, {
                'codigo': codigo_db,
                'fecha_generacion': fecha_gen.isoformat() if fecha_gen else None,
                'codigo_regenerado': bool(codigo_reg),
                'vigente': vigente,
            }
        except Exception:
            logger.exception("Error obteniendo código temporal usuario %s", user_id)
            return False, "Error al obtener código"

    def regenerar_codigo_temporal(self, user_id):
        """Regenera el código temporal de un usuario."""
        try:
            cur = self.conn.get_cursor()
            self.conn.autocommit = False
            cur.execute(
                "SELECT codigo_regenerado FROM empleados.dbo.usuarios WHERE id_usuario = ?",
                (user_id,)
            )
            if not cur.fetchone():
                self.conn.rollback()
                return False, "Usuario no encontrado"

            nuevo_codigo = ''.join(str(random.randint(0, 9)) for _ in range(6))
            cur.execute(
                "UPDATE empleados.dbo.usuarios "
                "SET codigo=?, fecha_codigo=GETDATE(), codigo_intentos_fallidos=0, "
                "codigo_regenerado=COALESCE(codigo_regenerado,0)+1 "
                "WHERE id_usuario=?",
                (nuevo_codigo, user_id)
            )
            self.conn.commit()
            logger.info("Código temporal regenerado para usuario %s", user_id)

            # Nota: El envío de emails fue removido. Los códigos se generan pero no se notifican por email.

            return True, {'codigo': nuevo_codigo, 'fecha_generacion': None, 'codigo_regenerado': True}

        except Exception:
            self.conn.rollback()
            logger.exception("Error regenerando código usuario %s", user_id)
            return False, "Error al regenerar código"
        finally:
            self.conn.autocommit = True

    def validar_codigo_temporal(self, username, codigo):
        """Valida el código temporal de un usuario (máx. 3 intentos, expira en 1 hora)."""
        try:
            cur = self.conn.get_cursor()
            self.conn.autocommit = False
            cur.execute(
                "SELECT id_usuario, codigo, fecha_codigo, codigo_intentos_fallidos "
                "FROM empleados.dbo.usuarios WHERE username = ?",
                (username,)
            )
            row = cur.fetchone()
            if not row:
                self.conn.rollback()
                return False, "Usuario no encontrado"

            user_id, codigo_db, fecha_gen, intentos = row
            intentos = intentos or 0

            if not codigo_db:
                self.conn.rollback()
                return False, "No hay código temporal asignado"

            if fecha_gen and datetime.now() > fecha_gen + timedelta(hours=1):
                self.conn.rollback()
                return False, "El código ha expirado. Contacte al administrador para regenerarlo."

            if intentos >= 3:
                self._invalidar_codigo(cur, user_id)
                self.conn.commit()
                return False, "Se alcanzó el límite de intentos. El código ha sido invalidado. Contacte al administrador."

            if codigo != codigo_db:
                nuevos_intentos = intentos + 1
                cur.execute(
                    "UPDATE empleados.dbo.usuarios "
                    "SET codigo_intentos_fallidos=? WHERE id_usuario=?",
                    (nuevos_intentos, user_id)
                )
                if nuevos_intentos >= 3:
                    self._invalidar_codigo(cur, user_id)
                    self.conn.commit()
                    return False, "Código incorrecto. Se alcanzó el límite de intentos y el código ha sido invalidado. Contacte al administrador."
                self.conn.commit()
                return False, f"Código incorrecto. Intentos restantes: {3 - nuevos_intentos}"

            self.conn.commit()
            return True, {'user_id': user_id, 'username': username}

        except Exception:
            try:
                self.conn.rollback()
            except Exception:
                pass
            logger.exception("Error validando código para '%s'", username)
            return False, "Error al validar código"
        finally:
            self.conn.autocommit = True

    def _invalidar_codigo(self, cur, user_id):
        """Limpia el código temporal y los intentos fallidos de un usuario."""
        cur.execute(
            "UPDATE empleados.dbo.usuarios "
            "SET codigo=NULL, fecha_codigo=NULL, codigo_intentos_fallidos=0 "
            "WHERE id_usuario=?",
            (user_id,)
        )

    def establecer_password(self, user_id, password):
        """Establece la contraseña definitiva tras validar el código temporal."""
        if len(password) < 8 or len(password) > 24:
            return False, "La contraseña debe tener entre 8 y 24 caracteres"
        if not re.search(r'[A-Z]', password):
            return False, "La contraseña debe contener al menos una letra mayúscula"
        if not re.search(r'[0-9]', password):
            return False, "La contraseña debe contener al menos un número"
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{};:\'",.<>?/\\|`~]', password):
            return False, "La contraseña debe contener al menos un símbolo especial"

        try:
            cur = self.conn.get_cursor()
            self.conn.autocommit = False
            cur.execute(
                "SELECT password_hash FROM empleados.dbo.usuarios WHERE id_usuario = ?",
                (user_id,)
            )
            if not cur.fetchone():
                self.conn.rollback()
                return False, "Usuario no encontrado"

            pwd_hash = generate_password_hash(password)
            cur.execute(
                "UPDATE empleados.dbo.usuarios "
                "SET password_hash=?, codigo=NULL, fecha_codigo=NULL, "
                "codigo_intentos_fallidos=0, fecha_ultimo_acceso=GETDATE() "
                "WHERE id_usuario=?",
                (pwd_hash, user_id)
            )
            self.conn.commit()
            logger.info("Contraseña establecida para usuario %s", user_id)
            return True, "Contraseña establecida exitosamente"

        except Exception:
            self.conn.rollback()
            logger.exception("Error estableciendo contraseña usuario %s", user_id)
            return False, "Error al establecer contraseña"
        finally:
            self.conn.autocommit = True