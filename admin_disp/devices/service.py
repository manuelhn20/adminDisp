import logging
from ..core.db import get_db_main, get_db_empleados
from werkzeug.security import generate_password_hash

logger = logging.getLogger(__name__)

# Importar helper de correlativos
try:
    from .correlativo_helper import generar_correlativos_para_asignacion
except ImportError:
    generar_correlativos_para_asignacion = None
    logger.warning('No se pudo importar generar_correlativos_para_asignacion')

# Estado mapping: número -> descripción
ESTADO_SIN_ASIGNAR = 0
ESTADO_ASIGNADO = 1
ESTADO_EN_REPARACION = 2
ESTADO_ELIMINADO = 3


def ensure_admin_exists():
    try:
        conn = get_db_empleados()
        cur = conn.cursor()
        u, p = "roussbel.medina", generate_password_hash("!1Qazwsx")
        
        cur.execute("IF NOT EXISTS (SELECT 1 FROM usuarios WHERE username=?) INSERT INTO usuarios (username, password_hash, fecha_creacion, estado) VALUES (?,?,GETDATE(),1) ELSE UPDATE usuarios SET password_hash=?,estado=1 WHERE username=?", (u, u, p, p, u))
        cur.execute("INSERT INTO usuarios_x_roles (fk_id_usuario, fk_id_rol, fecha_asignacion) SELECT u.id_usuario, r.id_rol, GETDATE() FROM usuarios u, roles r WHERE u.username=? AND r.nombre_rol='admin' AND NOT EXISTS (SELECT 1 FROM usuarios_x_roles WHERE fk_id_usuario=u.id_usuario AND fk_id_rol=r.id_rol)", (u,))
        
        conn.commit()
        conn.close()
    except:
        pass

class DeviceService:
    def __init__(self):
        self.conn = get_db_main()
        

    def has_column(self, table_name: str, column_name: str) -> bool:
        """Return True if the given column exists in the specified table."""
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = ? AND COLUMN_NAME = ?", (table_name, column_name))
            return bool(cur.fetchone())
        except Exception:
            return False

    def log_auditoria(self, usuario: str, accion: str, tabla_afectada: str, id_registro: int = None, descripcion: str = None):
        """Registra una acción en la tabla de auditoría"""
        try:
            cur = self.conn.cursor()
            cur.execute("""
                INSERT INTO auditoria (usuario, accion, tabla_afectada, id_registro, descripcion)
                VALUES (?, ?, ?, ?, ?)
            """, (usuario, accion, tabla_afectada, id_registro, descripcion))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error registrando auditoría: {str(e)}")
            # No lanzar excepción - el logging no debe bloquear operaciones

    # NOTE: Employee resolution now uses `empleados` via `get_empleado` and
    # `get_empleado_by_identidad`. Legacy identity DB access removed from this service.

    def list_available_devices(self):
        """Lista dispositivos disponibles para asignar (estado 0 y sin asignación activa)"""
        cur = self.conn.cursor()
        cur.execute("""
                    SELECT d.id_dispositivo, d.numero_serie, d.identificador, d.imei, d.imei2, d.direccion_mac,
                        d.ip_asignada, d.tamano, d.color, d.cargador, d.observaciones, ISNULL(d.estado, 0) as estado,
                        d.fk_id_modelo, d.fk_id_plan,
                                m.nombre_modelo, m.categoria, m.fk_id_marca as fk_id_marca, ma.nombre_marca
            FROM dispositivo d
                        LEFT JOIN modelo m ON m.id_modelo = d.fk_id_modelo
                        LEFT JOIN marca ma ON ma.id_marca = m.fk_id_marca
            WHERE d.estado = 0
              AND d.id_dispositivo NOT IN (
                SELECT fk_id_dispositivo FROM asignacion 
                WHERE fecha_fin_asignacion IS NULL OR fecha_fin_asignacion = ''
              )
            ORDER BY d.id_dispositivo DESC
        """)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def list_devices(self, sort_field: str = None, sort_dir: str = 'desc'):
        """Lista todos los dispositivos (excepto eliminados) con información de modelo y marca.

        Parámetros opcionales: `sort_field` puede ser uno de los campos permitidos y `sort_dir` 'asc'|'desc'.
        Esto evita inyección SQL construyendo la cláusula ORDER BY a partir de un whitelist.
        """
        # Whitelist de campos seguros para ordenar
        allowed = {
            'estado': 'ISNULL(d.estado, 0)',
            'categoria': 'm.categoria',
            'numero_serie': 'd.numero_serie',
            'nombre_modelo': 'm.nombre_modelo',
            'nombre_marca': 'ma.nombre_marca',
        }
        order_by = 'd.id_dispositivo DESC'
        if sort_field and sort_field in allowed:
            dir_s = 'ASC' if (str(sort_dir).lower() == 'asc') else 'DESC'
            order_by = f"{allowed[sort_field]} {dir_s}"
        elif sort_field == 'ip_asignada':
            dir_s = 'ASC' if (str(sort_dir).lower() == 'asc') else 'DESC'
            # Use TRY_CAST to avoid errors when IP parts are non-numeric or malformed
            order_by = (
                f"TRY_CAST(PARSENAME(d.ip_asignada, 4) AS INT) {dir_s}, "
                f"TRY_CAST(PARSENAME(d.ip_asignada, 3) AS INT) {dir_s}, "
                f"TRY_CAST(PARSENAME(d.ip_asignada, 2) AS INT) {dir_s}, "
                f"TRY_CAST(PARSENAME(d.ip_asignada, 1) AS INT) {dir_s}"
            )

        cur = self.conn.cursor()
        query = (
            """
            SELECT d.id_dispositivo, d.numero_serie, d.identificador, d.imei, d.imei2, d.direccion_mac,
                   d.ip_asignada, d.tamano, d.color, d.cargador, d.observaciones, ISNULL(d.estado, 0) as estado,
                   d.fk_id_modelo, m.nombre_modelo, m.categoria, m.fk_id_marca as fk_id_marca, ma.nombre_marca,
                   d.fk_id_plan
            FROM dispositivo d
            LEFT JOIN modelo m ON m.id_modelo = d.fk_id_modelo
            LEFT JOIN marca ma ON ma.id_marca = m.fk_id_marca
            WHERE d.estado != 3
            ORDER BY """
            + order_by
        )
        cur.execute(query)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def get_expiring_plans_notifications(self):
        """Devuelve una lista de dispositivos cuyo plan vence en 2 meses o menos.

        Cada elemento incluye: id_dispositivo, categoria, nombre_marca, nombre_modelo,
        numero_serie, fk_id_plan, fecha_fin (ISO), days_until_end (int).
        """
        cur = self.conn.cursor()
        # Selecciona dispositivos que tengan fk_id_plan y la fecha_fin del plan dentro de los próximos 2 meses
        cur.execute("""
            SELECT d.id_dispositivo, m.categoria, ma.nombre_marca, m.nombre_modelo,
               d.numero_serie, d.identificador, p.id_plan, p.fecha_fin, p.numero_linea,
               a.fk_id_empleado as fk_id_empleado,
               DATEDIFF(day, GETDATE(), p.fecha_fin) as days_until_end,
               DATEDIFF(day, p.fecha_fin, GETDATE()) as days_since_end
            FROM dispositivo d
            LEFT JOIN modelo m ON m.id_modelo = d.fk_id_modelo
            LEFT JOIN marca ma ON ma.id_marca = m.fk_id_marca
            JOIN planes p ON p.id_plan = d.fk_id_plan
            LEFT JOIN asignacion a ON a.fk_id_dispositivo = d.id_dispositivo AND (a.fecha_fin_asignacion IS NULL OR a.fecha_fin_asignacion = '')
            WHERE d.fk_id_plan IS NOT NULL
              AND p.fecha_fin IS NOT NULL
              AND p.fecha_fin <= DATEADD(month, 2, CONVERT(date, GETDATE()))
            ORDER BY p.fecha_fin ASC
        """)
        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]

        # Normalizar fecha a ISO y asegurar values
        for r in rows:
            try:
                fd = r.get('fecha_fin')
                if fd is None:
                    r['fecha_fin'] = None
                else:
                    if hasattr(fd, 'isoformat'):
                        r['fecha_fin'] = fd.isoformat()[:10]
                    else:
                        r['fecha_fin'] = str(fd)[:10]
            except Exception:
                r['fecha_fin'] = None
            try:
                r['days_until_end'] = int(r.get('days_until_end') or 0)
            except Exception:
                r['days_until_end'] = 0
            try:
                r['days_since_end'] = int(r.get('days_since_end') or 0)
            except Exception:
                r['days_since_end'] = 0

            # Add a notification creation date (today) and days_since_created = 0 (ephemeral notifications)
            from datetime import date
            today = date.today().isoformat()
            r['notified_date'] = today
            r['days_since_notified'] = 0
            # Resolve empleado nombre if fk_id_empleado present
            try:
                fk_emp = r.get('fk_id_empleado')
                if fk_emp:
                    name = self._get_empleado_nombre(fk_emp)
                    r['empleado_nombre'] = name or ''
                else:
                    r['empleado_nombre'] = ''
            except Exception:
                r['empleado_nombre'] = ''
            # Ensure numero_linea is present (from planes table)
            try:
                r['numero_linea'] = r.get('numero_linea') or ''
            except Exception:
                r['numero_linea'] = ''

        return rows

    def get_device(self, device_id):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT d.id_dispositivo, d.numero_serie, d.identificador, d.imei, d.imei2, d.direccion_mac,
                   d.ip_asignada, d.tamano, d.color, d.cargador, d.observaciones, ISNULL(d.estado, 0) as estado,
                   d.fk_id_modelo, m.nombre_modelo, m.categoria, m.fk_id_marca as fk_id_marca, ma.nombre_marca,
                   d.fk_id_plan, d.fecha_obt,
                   a.fk_id_empleado
            FROM dispositivo d
            LEFT JOIN modelo m ON m.id_modelo = d.fk_id_modelo
            LEFT JOIN marca ma ON ma.id_marca = m.fk_id_marca
            LEFT JOIN asignacion a ON a.fk_id_dispositivo = d.id_dispositivo 
                AND (a.fecha_fin_asignacion IS NULL OR a.fecha_fin_asignacion = '')
            WHERE d.id_dispositivo = ?
        """, (device_id,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [c[0] for c in cur.description]
        result = dict(zip(cols, row))
        
        # Normalize fecha field for clients: handle both fecha_obt and fecha_obtencion
        # Ensure dates are in ISO format (YYYY-MM-DD) for input[type=date]
        fecha_value = None
        if 'fecha_obt' in result and result.get('fecha_obt'):
            fecha_value = result['fecha_obt']
        elif 'fecha_obtencion' in result and result.get('fecha_obtencion'):
            fecha_value = result['fecha_obtencion']
        
        # Normalize to ISO string if it's a date object
        if fecha_value:
            try:
                if hasattr(fecha_value, 'isoformat'):
                    fecha_value = fecha_value.isoformat()
                elif isinstance(fecha_value, str):
                    # Try to parse and re-format to ensure ISO
                    from datetime import datetime
                    parsed = datetime.fromisoformat(fecha_value.split()[0])  # handle datetime strings
                    fecha_value = parsed.date().isoformat()
            except Exception:
                fecha_value = None
        
        # Always expose fecha_obt for clients
        result['fecha_obt'] = fecha_value or ''
        
        # If device has an assigned employee, fetch employee data
        if result.get('fk_id_empleado'):
            try:
                empleado = self.get_empleado(result['fk_id_empleado'])
                if empleado:
                    result['empleado_nombre'] = empleado.get('nombre_completo', '')
                    result['empleado_puesto'] = empleado.get('puesto', '')
                    result['empleado_empresa'] = empleado.get('empresa', '')
            except Exception as e:
                logger.warning(f"Error obteniendo datos de empleado para dispositivo {device_id}: {e}")
        
        return result

    def get_device_by_identificador(self, identificador: str):
        """Obtiene un dispositivo por su identificador (case-insensitive).
        Retorna el diccionario del dispositivo o None si no existe."""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT d.*, ISNULL(d.estado, 0) as estado,
                   m.nombre_modelo, m.categoria, m.fk_id_marca as fk_id_marca, ma.nombre_marca
            FROM dispositivo d
            LEFT JOIN modelo m ON m.id_modelo = d.fk_id_modelo
            LEFT JOIN marca ma ON ma.id_marca = m.fk_id_marca
            WHERE LOWER(d.identificador) = LOWER(?)
        """, (identificador.strip(),))
        row = cur.fetchone()
        if not row:
            return None
        cols = [c[0] for c in cur.description]
        return dict(zip(cols, row))

    def get_device_suggestions_by_modelo(self, modelo_id: int):
        """Obtiene dispositivos existentes con el mismo modelo para mostrar sugerencias.
        Incluye componentes principales y agrupa por características para evitar duplicados.
        Si hay múltiples dispositivos con la misma config (CPU/RAM/DISCO), retorna UNO de cada grupo."""
        cur = self.conn.cursor()
        
        # Obtener TODOS los dispositivos del modelo (sin TOP limit)
        # pero ordenados por fecha descendente
        cur.execute("""
            SELECT d.*, ISNULL(d.estado, 0) as estado,
                   m.nombre_modelo, m.categoria, m.fk_id_marca, ma.nombre_marca
            FROM dispositivo d
            JOIN modelo m ON m.id_modelo = d.fk_id_modelo
            LEFT JOIN marca ma ON ma.id_marca = m.fk_id_marca
            WHERE d.fk_id_modelo = ? AND ISNULL(d.estado, 0) != 3
            ORDER BY d.fecha_obt DESC, d.id_dispositivo DESC
        """, (modelo_id,))
        cols = [c[0] for c in cur.description]
        all_devices = [dict(zip(cols, r)) for r in cur.fetchall()]
        
        # Para cada dispositivo, obtener sus componentes principales
        for dev in all_devices:
            dev_id = dev.get('id_dispositivo')
            categoria = (dev.get('categoria') or '').lower()
            
            # Obtener componentes
            cur.execute("""
                SELECT c.*, ma.nombre_marca as componente_marca, mo.nombre_modelo as componente_modelo
                FROM componente c
                LEFT JOIN marca ma ON ma.id_marca = c.fk_id_marca
                LEFT JOIN modelo mo ON mo.id_modelo = c.fk_id_modelo
                WHERE c.fk_id_dispositivo = ? AND ISNULL(c.estado, 0) != 3
            """, (dev_id,))
            comp_cols = [c[0] for c in cur.description]
            componentes = [dict(zip(comp_cols, r)) for r in cur.fetchall()]
            
            # Filtrar según categoría
            if categoria == 'laptop':
                dev['componentes'] = [c for c in componentes if c.get('tipo_componente') in (0, '0')]
            elif categoria in ('celular', 'tablet'):
                dev['componentes'] = [c for c in componentes if c.get('tipo_componente') in (0, 1, 2, '0', '1', '2')]
            else:
                dev['componentes'] = []
        
        # Deduplicar por características: agrupar dispositivos similares
        # Retornar un representante de cada grupo + contar cuántos hay
        grouped = {}
        for dev in all_devices:
            # Crear clave por componentes (CPU modelo + RAM capacidad + DISCO capacidad)
            key_parts = []
            for comp in dev.get('componentes', []):
                tipo = comp.get('tipo_componente')
                if tipo == 0:  # CPU
                    modelo = comp.get('componente_modelo') or comp.get('nombre_modelo') or ''
                    key_parts.append(f"cpu:{modelo}")
                elif tipo == 1:  # RAM
                    capacidad = comp.get('capacidad') or ''
                    key_parts.append(f"ram:{capacidad}")
                elif tipo == 2:  # DISCO
                    capacidad = comp.get('capacidad') or ''
                    key_parts.append(f"disco:{capacidad}")
            
            # Si no hay componentes, agrupar por dispositivo ID
            if not key_parts:
                key_parts = [f"nocomp:{dev.get('id_dispositivo')}"]
            
            key = '|'.join(sorted(key_parts))
            
            if key not in grouped:
                grouped[key] = {
                    'representative': dev,
                    'count': 0,
                    'similar_ids': []
                }
            
            grouped[key]['count'] += 1
            grouped[key]['similar_ids'].append(dev.get('id_dispositivo'))
        
        # Retornar solo representantes, pero con info de cuántos hay
        result = []
        for group_info in grouped.values():
            dev = group_info['representative']
            dev['_similar_count'] = group_info['count']
            dev['_similar_ids'] = group_info['similar_ids']
            result.append(dev)
        
        # Limitar a 10 grupos (para no saturar UI)
        return result[:10]

    def list_components(self, device_id):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT c.*, ma.nombre_marca as nombre_marca, mo.nombre_modelo as nombre_modelo
            FROM componente c
            LEFT JOIN marca ma ON ma.id_marca = c.fk_id_marca
            LEFT JOIN modelo mo ON mo.id_modelo = c.fk_id_modelo
            WHERE c.fk_id_dispositivo = ? AND ISNULL(c.estado, 0) != 3
            ORDER BY c.id_componente
        """, (device_id,))
        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        # Map numeric tipo_componente to human-readable values for the UI
        for r in rows:
            try:
                tc = r.get('tipo_componente')
                if tc in (0, '0'):
                    r['tipo_componente'] = 'CPU'
                elif tc in (1, '1'):
                    r['tipo_componente'] = 'RAM'
                elif tc in (2, '2'):
                    r['tipo_componente'] = 'DISCO'
            except Exception:
                pass
            # Map stored disco codes to full display labels
            try:
                td = r.get('tipo_disco')
                if isinstance(td, str):
                    tdl = td.strip().lower()
                    if 'nvme' in tdl:
                        r['tipo_disco'] = 'SSD NVMe'
                    elif 'sata' in tdl:
                        r['tipo_disco'] = 'SSD SATA'
                    else:
                        r['tipo_disco'] = td
            except Exception:
                pass
        return rows

    def create_componente(self,
                          fk_id_dispositivo: int,
                          tipo_componente: str,
                          frecuencia: int | None = None,
                          tipo_memoria: str | None = None,
                          tipo_modulo: str | None = None,
                          capacidad: int | None = None,
                          tipo_disco: str | None = None,
                          fk_id_marca: int | None = None,
                          fk_id_modelo: int | None = None,
                          numero_serie: str | None = None):
        """Crea un registro en la tabla `componente`.

        Valida los campos relevantes y devuelve el id del componente creado.
        """
        if not fk_id_dispositivo:
            raise ValueError('fk_id_dispositivo es requerido')
        if not tipo_componente:
            raise ValueError('tipo_componente es requerido')

        # Accept either textual values ('RAM'/'DISCO') or numeric codes (1 for RAM, 2 for DISCO)
        tipo_code = None
        if isinstance(tipo_componente, str):
            tstr = tipo_componente.strip().upper()
            if tstr == 'CPU':
                tipo_code = 0
            elif tstr == 'RAM':
                tipo_code = 1
            elif tstr == 'DISCO':
                tipo_code = 2
            else:
                # try numeric string
                try:
                    tipo_code = int(tipo_componente)
                except Exception:
                    tipo_code = None
        elif isinstance(tipo_componente, (int, float)):
            try:
                tipo_code = int(tipo_componente)
            except Exception:
                tipo_code = None

        if tipo_code not in (0, 1, 2):
            raise ValueError("tipo_componente inválido: debe ser 'CPU', 'RAM' o 'DISCO' (o 0/1/2)" )

        # Si es CPU (0) asegurar que no exista ya una CPU asociada al dispositivo
        if tipo_code == 0:
            cur = self.conn.cursor()
            cur.execute("SELECT COUNT(1) FROM componente WHERE fk_id_dispositivo = ? AND tipo_componente = 0", (int(fk_id_dispositivo),))
            cnt = cur.fetchone()[0]
            if cnt and cnt > 0:
                raise ValueError('Ya existe un CPU asignado a este dispositivo (solo uno permitido)')

        # Coerce numeric fields
        try:
            frecuencia_val = None
            if frecuencia not in (None, '', False):
                # Para CPU se espera formato 2.40 o 2,40 (GHz) -> almacenar como int 240 (GHz*100)
                if tipo_code == 0:
                    s = str(frecuencia).strip()
                    s = s.replace(',', '.')
                    try:
                        f = float(s)
                        frecuencia_val = int(round(f * 100))
                    except Exception:
                        # si ya enviaron número entero (ej: 240) lo tomamos tal cual
                        try:
                            frecuencia_val = int(s)
                        except Exception:
                            frecuencia_val = None
                else:
                    # Para RAM u otros, se espera MHz integer (ej 2400)
                    frecuencia_val = int(float(str(frecuencia).strip()))
        except Exception:
            frecuencia_val = None
        try:
            capacidad_val = int(capacidad) if capacidad not in (None, '', False) else None
        except Exception:
            capacidad_val = None

        try:
            fk_marca_val = int(fk_id_marca) if fk_id_marca not in (None, '', False) else None
        except Exception:
            fk_marca_val = None

        cur = self.conn.cursor()
        try:
            # Normalize tipo_disco to short stored codes: 'NVMe' or 'SATA' when applicable
            tipo_disco_val = None
            if isinstance(tipo_disco, str) and tipo_disco.strip():
                _td = tipo_disco.strip()
                _td_l = _td.lower()
                if 'nvme' in _td_l:
                    tipo_disco_val = 'NVMe'
                elif 'sata' in _td_l:
                    tipo_disco_val = 'SATA'
                else:
                    tipo_disco_val = _td

            # Determine whether the componente table has an 'estado' column
            has_estado = False
            try:
                has_estado = self.has_column('componente', 'estado')
            except Exception:
                has_estado = False

            try:
                fk_modelo_val = int(fk_id_modelo) if fk_id_modelo not in (None, '', False) else None
            except Exception:
                fk_modelo_val = None

            columns = ['fk_id_dispositivo', 'tipo_componente', 'frecuencia', 'tipo_memoria', 'tipo_modulo', 'capacidad', 'tipo_disco', 'fk_id_marca', 'fk_id_modelo', 'numero_serie']
            params = [int(fk_id_dispositivo), tipo_code, frecuencia_val, tipo_memoria, tipo_modulo, capacidad_val, tipo_disco_val, fk_marca_val, fk_modelo_val, (numero_serie or None)]

            if has_estado:
                columns.append('estado')
                params.append(ESTADO_SIN_ASIGNAR)

            placeholders = ', '.join(['?'] * len(params))
            columns_sql = ', '.join(columns)
            sql = "INSERT INTO componente (" + columns_sql + ") OUTPUT INSERTED.id_componente VALUES (" + placeholders + ")"
            cur.execute(sql, params)
            result = cur.fetchone()
            if result is None:
                raise ValueError("No se pudo crear el componente")
            new_id = int(result[0])
            self.conn.commit()
            return new_id
        except Exception:
            self.conn.rollback()
            raise

    def get_componente(self, componente_id: int):
        """Obtiene un componente por su ID."""
        cur = self.conn.cursor()
        try:
            cur.execute("""
                 SELECT id_componente, fk_id_dispositivo, tipo_componente, frecuencia, 
                     tipo_memoria, tipo_modulo, capacidad, tipo_disco, numero_serie, fk_id_marca, fk_id_modelo, ISNULL(estado, 0) as estado, observaciones
                    FROM componente
                    WHERE id_componente = ?
                """, (componente_id,))
        except Exception as e:
            # Fallback for databases where fk_id_modelo column does not exist yet.
            try:
                logger = logging.getLogger('admin_disp.dispositivos')
                logger.exception('Error selecting fk_id_modelo for componente %s; retrying without that column: %s', componente_id, e)
            except Exception:
                pass
            cur.execute("""
                 SELECT id_componente, fk_id_dispositivo, tipo_componente, frecuencia, 
                     tipo_memoria, tipo_modulo, capacidad, tipo_disco, numero_serie, fk_id_marca, ISNULL(estado,0) as estado, observaciones
                    FROM componente
                    WHERE id_componente = ?
                """, (componente_id,))
        cols = [c[0] for c in cur.description]
        row = cur.fetchone()
        if not row:
            return None
        result = dict(zip(cols, row))
        # Ensure fk_id_modelo present in result for compatibility with frontend
        if 'fk_id_modelo' not in result:
            result['fk_id_modelo'] = None
        # Normalize tipo_componente to text
        try:
            tc = result.get('tipo_componente')
            if tc in (0, '0'):
                result['tipo_componente'] = 'CPU'
            if tc in (1, '1'):
                result['tipo_componente'] = 'RAM'
            elif tc in (2, '2'):
                result['tipo_componente'] = 'DISCO'
        except Exception:
            pass
        # Normalize tipo_disco to display labels
        try:
            td = result.get('tipo_disco')
            if isinstance(td, str):
                tdl = td.strip().lower()
                if 'nvme' in tdl:
                    result['tipo_disco'] = 'SSD NVMe'
                elif 'sata' in tdl:
                    result['tipo_disco'] = 'SSD SATA'
        except Exception:
            pass
        # Get marca name if fk_id_marca exists
        try:
            if result.get('fk_id_marca'):
                cur.execute("SELECT nombre_marca FROM marca WHERE id_marca = ?", (result['fk_id_marca'],))
                marca_row = cur.fetchone()
                result['nombre_marca'] = marca_row[0] if marca_row else None
        except:
            result['nombre_marca'] = None
        # Get modelo name if fk_id_modelo exists
        try:
            if result.get('fk_id_modelo'):
                try:
                    cur.execute("SELECT nombre_modelo FROM modelo WHERE id_modelo = ?", (result['fk_id_modelo'],))
                    modelo_row = cur.fetchone()
                    result['nombre_modelo'] = modelo_row[0] if modelo_row else None
                except Exception:
                    result['nombre_modelo'] = None
        except Exception:
            result['nombre_modelo'] = None
        return result

    def update_componente(self,
                         componente_id: int,
                         tipo_componente: str | None = None,
                         frecuencia: int | None = None,
                         tipo_memoria: str | None = None,
                         tipo_modulo: str | None = None,
                         capacidad: int | None = None,
                         tipo_disco: str | None = None,
                         fk_id_marca: int | None = None,
                         fk_id_modelo: int | None = None,
                         estado: int | None = None,
                         numero_serie: str | None = None,
                         observaciones: str | None = None):
        """Actualiza un componente existente."""
        if not componente_id:
            raise ValueError('componente_id es requerido')

        cur = self.conn.cursor()
        try:
            # Si se intenta actualizar el número de serie, validar que no sea duplicado en el mismo dispositivo
            if numero_serie is not None and numero_serie:
                numero_serie_clean = str(numero_serie).strip()
                if numero_serie_clean:
                    # Obtener device_id y tipo del componente actual
                    cur.execute("SELECT fk_id_dispositivo, tipo_componente FROM componente WHERE id_componente = ?", (componente_id,))
                    row = cur.fetchone()
                    if row:
                        fk_dev = row[0]
                        tipo_actual = row[1]
                        # Verificar que no exista otro componente del mismo tipo en el mismo dispositivo con el mismo número de serie
                        cur.execute("""
                            SELECT COUNT(1) FROM componente 
                            WHERE fk_id_dispositivo = ? 
                              AND tipo_componente = ? 
                              AND numero_serie = ? 
                              AND id_componente != ?
                        """, (fk_dev, tipo_actual, numero_serie_clean, componente_id))
                        cnt = cur.fetchone()[0]
                        if cnt and cnt > 0:
                            raise ValueError(f'Ya existe un componente del mismo tipo con ese número de serie en este dispositivo')
            
            # Build dynamic UPDATE statement (keep updates and params in sync)
            updates = []
            params = []

            if tipo_componente is not None:
                # Convert text to code if needed
                if isinstance(tipo_componente, str) and tipo_componente.strip():
                    tc = tipo_componente.strip().upper()
                    if tc == 'RAM': tipo_code = 1
                    elif tc == 'DISCO': tipo_code = 2
                    elif tc == 'CPU': tipo_code = 0
                    else: tipo_code = None
                else:
                    try:
                        tipo_code = int(tipo_componente) if tipo_componente is not None else None
                    except Exception:
                        tipo_code = None

                if tipo_code not in (0, 1, 2):
                    raise ValueError("tipo_componente inválido: debe ser 'CPU', 'RAM' o 'DISCO'")
                # If changing to CPU ensure uniqueness for this device
                if tipo_code == 0:
                    # find device id for this component
                    cur.execute("SELECT fk_id_dispositivo FROM componente WHERE id_componente = ?", (componente_id,))
                    row = cur.fetchone()
                    fk_dev = row[0] if row else None
                    if fk_dev:
                        cur.execute("SELECT COUNT(1) FROM componente WHERE fk_id_dispositivo = ? AND tipo_componente = 0 AND id_componente != ?", (fk_dev, componente_id))
                        cnt = cur.fetchone()[0]
                        if cnt and cnt > 0:
                            raise ValueError('Ya existe un CPU asignado a este dispositivo (solo uno permitido)')
                updates.append("tipo_componente = ?")
                params.append(tipo_code)

            if frecuencia is not None:
                # Handle CPU frequency input (e.g. '2.40' or '2,40') -> store as int*100
                try:
                    freq_val = None
                    if frecuencia not in (None, '', False):
                        # If string contains comma or dot and looks like GHz, parse
                        s = str(frecuencia).strip()
                        if ',' in s or '.' in s:
                            s2 = s.replace(',', '.')
                            try:
                                f = float(s2)
                                freq_val = int(round(f * 100))
                            except Exception:
                                try:
                                    freq_val = int(s)
                                except Exception:
                                    freq_val = None
                        else:
                            # assume integer MHz provided
                            freq_val = int(float(s))
                except:
                    freq_val = None
                updates.append("frecuencia = ?")
                params.append(freq_val)

            if tipo_memoria is not None:
                updates.append("tipo_memoria = ?")
                params.append(tipo_memoria if tipo_memoria else None)

            if tipo_modulo is not None:
                updates.append("tipo_modulo = ?")
                params.append(tipo_modulo if tipo_modulo else None)

            if capacidad is not None:
                try:
                    cap_val = int(capacidad) if capacidad else None
                except:
                    cap_val = None
                updates.append("capacidad = ?")
                params.append(cap_val)

            if tipo_disco is not None:
                tipo_disco_val = None
                if isinstance(tipo_disco, str) and tipo_disco.strip():
                    _td = tipo_disco.strip()
                    _td_l = _td.lower()
                    if 'nvme' in _td_l:
                        tipo_disco_val = 'NVMe'
                    elif 'sata' in _td_l:
                        tipo_disco_val = 'SATA'
                    else:
                        tipo_disco_val = _td
                updates.append("tipo_disco = ?")
                params.append(tipo_disco_val)

            if fk_id_marca is not None:
                try:
                    marca_val = int(fk_id_marca) if fk_id_marca else None
                except:
                    marca_val = None
                updates.append("fk_id_marca = ?")
                params.append(marca_val)

            if fk_id_modelo is not None:
                try:
                    modelo_val = int(fk_id_modelo) if fk_id_modelo else None
                except Exception:
                    modelo_val = None
                updates.append("fk_id_modelo = ?")
                params.append(modelo_val)

            if estado is not None:
                try:
                    estado_val = int(estado) if estado is not None and str(estado) != '' else None
                except Exception:
                    estado_val = None
                updates.append("estado = ?")
                params.append(estado_val)

            if numero_serie is not None:
                updates.append("numero_serie = ?")
                params.append(numero_serie if numero_serie else None)

            if observaciones is not None:
                updates.append("observaciones = ?")
                params.append(observaciones if observaciones else None)

            if not updates:
                return True  # Nothing to update

            set_clause = ', '.join(updates)
            sql = "UPDATE componente SET " + set_clause + " WHERE id_componente = ?"
            params.append(componente_id)
            
            cur.execute(sql, params)
            self.conn.commit()
            return True
        except Exception:
            self.conn.rollback()
            raise

    def delete_componente(self, componente_id: int):
        """Elimina un componente por su ID."""
        if not componente_id:
            raise ValueError('componente_id es requerido')
        
        cur = self.conn.cursor()
        try:
            cur.execute("DELETE FROM componente WHERE id_componente = ?", (componente_id,))
            self.conn.commit()
            return True
        except Exception:
            self.conn.rollback()
            raise

    def list_peripherals(self, device_id):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT * FROM periferico WHERE fk_id_dispositivo = ? ORDER BY id_periferico
        """, (device_id,))
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def list_devices_without_plan(self):
        """Lista dispositivos tipo 'Celular' que no tienen un plan vinculado en la asignación activa,
        o que no tienen asignación activa.
        """
        cur = self.conn.cursor()
        cur.execute("""
             SELECT d.id_dispositivo, d.numero_serie, d.identificador, d.imei, d.imei2, d.direccion_mac,
                 d.ip_asignada, d.tamano, d.color, d.cargador, d.observaciones, ISNULL(d.estado,0) as estado,
                 d.fk_id_modelo, m.nombre_modelo, m.categoria, m.fk_id_marca as fk_id_marca, ma.nombre_marca,
                 a.id_asignacion, a.fk_id_empleado, a.fecha_inicio_asignacion
             FROM dispositivo d
            JOIN modelo m ON m.id_modelo = d.fk_id_modelo
            LEFT JOIN marca ma ON ma.id_marca = m.fk_id_marca
            LEFT JOIN asignacion a ON a.fk_id_dispositivo = d.id_dispositivo AND (a.fecha_fin_asignacion IS NULL OR a.fecha_fin_asignacion = '')
                        WHERE m.categoria = 'Celular'
                            AND d.fk_id_plan IS NULL
                            AND ISNULL(d.estado,0) != 3
            ORDER BY d.id_dispositivo DESC
        """)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def link_plan_to_device(self, device_id: int, plan_id: int, fecha_inicio=None):
        """Vincula un plan a un dispositivo.

        Mueve la asociación del plan al nivel de `dispositivo.fk_id_plan`. 
        Devuelve el `id_dispositivo` actualizado.
        """
        cur = self.conn.cursor()
        try:
            # If the caller provided a plan object (with temporary fields), create using those values.
            from collections.abc import Mapping
            if isinstance(plan_id, Mapping):
                plan_obj = plan_id
                numero_linea_val = plan_obj.get('numero_linea') or plan_obj.get('numeroLinea') or plan_obj.get('numero')
                # Allow extension fields coming from frontend
                ext_val = plan_obj.get('extension') or plan_obj.get('country_code') or plan_obj.get('codigo_pais') or plan_obj.get('prefijo')
                # Normalize: if numero_linea_val is short or missing leading +, combine with ext_val
                try:
                    if numero_linea_val:
                        s = str(numero_linea_val).strip()
                        # if starts with + assume complete
                        if not s.startswith('+') and ext_val:
                            # strip non-digits
                            import re
                            ed = re.sub(r"\D", "", str(ext_val))
                            nd = re.sub(r"\D", "", s)
                            if ed:
                                numero_linea_val = f"+{ed}{nd}"
                            else:
                                # fallback: if numero looks short and no ext digits, add +504
                                if len(nd) < 8:
                                    numero_linea_val = f"+504{nd}"
                                else:
                                    numero_linea_val = f"+{nd}"
                        elif not s.startswith('+') and not ext_val:
                            # no ext provided: if too short, add default +504
                            import re
                            nd = re.sub(r"\D", "", s)
                            if len(nd) < 8:
                                numero_linea_val = f"+504{nd}"
                            else:
                                numero_linea_val = f"+{nd}"
                    else:
                        numero_linea_val = None
                except Exception:
                    pass
                fecha_inicio_val = plan_obj.get('fecha_inicio') or plan_obj.get('fechaInicio') or fecha_inicio
                fecha_fin_val = plan_obj.get('fecha_fin') or plan_obj.get('fechaFin') or None
                costo_val = plan_obj.get('costo_plan') if plan_obj.get('costo_plan') is not None else plan_obj.get('costo')
                moneda_val = plan_obj.get('moneda_plan') or plan_obj.get('moneda') or 'USD'
                if not numero_linea_val:
                    raise ValueError('numero_linea es requerido para crear el plan')
                # Ensure fecha_inicio_val has a sensible default handled by create_plane caller
                try:
                    new_plan_id = self.create_plane(numero_linea_val, fecha_inicio_val, fecha_fin_val, costo_val if costo_val is not None else 0, moneda_val)
                    resolved_plan_id = int(new_plan_id)
                    logger.info('Plan creado desde objeto temporal id=%s numero_linea=%s', resolved_plan_id, numero_linea_val)
                except Exception as e:
                    raise ValueError(f"No se pudo crear el plan desde datos temporales: {e}")
            else:
                # Resolver plan: aceptar id_plan (int) o numero_linea (string).
                # Intentos, en orden:
                # 1) Buscar por id_plan exacto
                # 2) Buscar por numero_linea exacto (case-insensitive)
                # 3) Buscar por numero_linea después de limpiar espacios y prefijos
                # 4) Buscar por LIKE si contiene el valor
                resolved_plan_id = None

            # 1) id_plan exacto
            try:
                cur.execute("SELECT id_plan FROM planes WHERE id_plan = ?", (plan_id,))
                row = cur.fetchone()
                if row:
                    resolved_plan_id = int(row[0])
            except Exception:
                row = None

            # Normalize input for subsequent searches
            plan_input_str = ''
            try:
                plan_input_str = str(plan_id).strip()
            except Exception:
                plan_input_str = ''

            # 2) numero_linea exacto (case-insensitive)
            if resolved_plan_id is None and plan_input_str:
                try:
                    cur.execute("SELECT id_plan FROM planes WHERE LOWER(numero_linea) = LOWER(?)", (plan_input_str,))
                    row = cur.fetchone()
                    if row:
                        resolved_plan_id = int(row[0])
                except Exception:
                    pass

            # 3) numero_linea cleaned (remove non-alphanum edges)
            if resolved_plan_id is None and plan_input_str:
                cleaned = ''.join(ch for ch in plan_input_str if ch.isalnum())
                if cleaned and cleaned != plan_input_str:
                    try:
                        cur.execute("SELECT id_plan FROM planes WHERE LOWER(REPLACE(numero_linea, ' ', '')) = LOWER(?)", (cleaned,))
                        row = cur.fetchone()
                        if row:
                            resolved_plan_id = int(row[0])
                    except Exception:
                        pass

            # 4) LIKE fallback (dangerous but last resort)
            if resolved_plan_id is None and plan_input_str:
                try:
                    like_pattern = f"%{plan_input_str}%"
                    cur.execute("SELECT TOP 1 id_plan FROM planes WHERE numero_linea LIKE ?", (like_pattern,))
                    row = cur.fetchone()
                    if row:
                        resolved_plan_id = int(row[0])
                except Exception:
                    pass

            if resolved_plan_id is None:
                # Si no existe el plan, intentar crearlo automáticamente usando el numero_linea
                # (caso: la transacción crea el plan y luego intenta vincular). Usamos valores
                # por defecto mínimos: fecha_inicio si fue provista o hoy, fecha_fin=None, costo=0.
                if not plan_input_str:
                    raise ValueError(f"Plan '{plan_id}' no encontrado (intentados id y numero_linea)")
                try:
                    from datetime import date
                    fecha_inicio_use = fecha_inicio if fecha_inicio else date.today().isoformat()
                    # create_plane espera costo_plan no-nulo; usamos 0 como placeholder
                    new_plan_id = self.create_plane(plan_input_str, fecha_inicio_use, None, 0, 'USD')
                    resolved_plan_id = int(new_plan_id)
                    logger.info('Plan creado automáticamente id=%s para numero_linea=%s', resolved_plan_id, plan_input_str)
                except Exception as e:
                    # No se pudo crear el plan; informar al caller
                    raise ValueError(f"Plan '{plan_id}' no encontrado y no se pudo crear: {e}")

            # Actualizar dispositivo con el plan resuelto
            cur.execute("UPDATE dispositivo SET fk_id_plan = ? WHERE id_dispositivo = ?", (resolved_plan_id, device_id))
            if cur.rowcount == 0:
                raise ValueError(f"Dispositivo {device_id} no encontrado")
            self.conn.commit()
            # Return both device_id and resolved plan id so caller/route can inform the UI
            return {'device_id': int(device_id), 'id_plan': resolved_plan_id}
        except Exception:
            self.conn.rollback()
            raise

    def _get_or_create_marca(self, nombre_marca: str):
        cur = self.conn.cursor()
        cur.execute("SELECT id_marca FROM marca WHERE nombre_marca = ?", (nombre_marca,))
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute("INSERT INTO marca (nombre_marca) OUTPUT INSERTED.id_marca VALUES (?)", (nombre_marca,))
        result = cur.fetchone()
        if result is None:
            raise ValueError("No se pudo crear la marca")
        self.conn.commit()
        return int(result[0])

    def _get_or_create_modelo(self, nombre_modelo: str, categoria: str, fk_id_marca: int):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT id_modelo FROM modelo
            WHERE nombre_modelo = ? AND fk_id_marca = ?
        """, (nombre_modelo, fk_id_marca))
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute(
            "INSERT INTO modelo (nombre_modelo, categoria, fk_id_marca) OUTPUT INSERTED.id_modelo VALUES (?, ?, ?)",
            (nombre_modelo, categoria, fk_id_marca)
        )
        result = cur.fetchone()
        if result is None:
            raise ValueError("No se pudo crear el modelo")
        self.conn.commit()
        return int(result[0])

    def transfer_devices_between_empleados(self, fk_from_empleado: int, fk_to_empleado: int, device_ids: list, usuario_id: int = None):
        """Transfiere dispositivos de un empleado a otro.
        - Marca fecha_fin_asignacion = GETDATE() para las asignaciones activas del empleado origen y dispositivos indicados.
        - Crea nuevas filas de asignacion para el empleado receptor con fecha_inicio_asignacion = GETDATE().
        Operación atómica (transactional) para trazabilidad.
        """
        if not device_ids:
            raise ValueError('No se especificaron dispositivos')

        # Normalize and validate inputs to avoid NULL inserts
        try:
            fk_from_empleado = int(fk_from_empleado) if fk_from_empleado is not None and str(fk_from_empleado) != '' else None
        except Exception:
            fk_from_empleado = None
        try:
            fk_to_empleado = int(fk_to_empleado) if fk_to_empleado is not None and str(fk_to_empleado) != '' else None
        except Exception:
            fk_to_empleado = None

        if not fk_to_empleado:
            raise ValueError('Empleado receptor inválido')

        # ensure device ids are ints
        try:
            device_ids = [int(x) for x in device_ids]
        except Exception:
            raise ValueError('device_ids inválidos')

        cur = self.conn.cursor()
        try:
            # Primero obtener el tipo de cada dispositivo que será transferido
            placeholders = ','.join(['?'] * len(device_ids))
            query = (
                """
                SELECT d.id_dispositivo, m.categoria
                FROM dispositivo d
                LEFT JOIN modelo m ON m.id_modelo = d.fk_id_modelo
                WHERE d.id_dispositivo IN ("""
                + placeholders
                + ")"
            )
            cur.execute(query, device_ids)
            tipo_rows = cur.fetchall()
            tipos_por_device = { r[0]: (r[1] or '') for r in tipo_rows }

            # Verificar si alguno de los dispositivos tiene un reclamo activo
            # (consideramos activo si r.fecha_fin_reclamo IS NULL o r.estado_proceso = 0)
            try:
                query = (
                    """
                    SELECT DISTINCT a.fk_id_dispositivo
                    FROM asignacion a
                    JOIN reclamo_seguro r ON r.fk_id_asignacion = a.id_asignacion
                    WHERE a.fk_id_dispositivo IN ("""
                    + placeholders
                    + """)
                      AND (r.fecha_fin_reclamo IS NULL OR r.estado_proceso = 0)
                    """
                )
                cur.execute(query, device_ids)
                reclamo_rows = cur.fetchall()
                if reclamo_rows:
                    # Do not expose internal IDs in error messages returned to clients.
                    # Provide a generic, non-identifying error message instead.
                    raise ValueError('No se puede transferir: uno o más dispositivos tienen reclamos en proceso. Verifique la lista de reclamos antes de intentar la transferencia.')
            except ValueError:
                # Propagar ValueError para manejarlo arriba
                raise
            except Exception:
                # Si la verificación falla por algún motivo, no bloquear la operación silenciosamente;
                # preferimos propagar el error para que el caller lo maneje/vea.
                raise

            # Tipos que solo se permiten 1 por empleado
            # Añadido 'Tablet' según nueva política: máximo 1 por empleado
            tipos_restringidos = ('Laptop', 'Celular', 'Tablet', 'Monitor', 'Mouse', 'Teclado', 'Telefono VoIP')

            # Contar cuántos dispositivos entrantes por tipo
            incoming_counts = {}
            for dev in device_ids:
                t = tipos_por_device.get(dev, '')
                if t in tipos_restringidos:
                    incoming_counts[t] = incoming_counts.get(t, 0) + 1

            # Validar contra las asignaciones activas del empleado destino
            conflicts = []
            for tipo, inc_count in incoming_counts.items():
                # Contar asignaciones activas del mismo tipo para el empleado destino
                cur.execute("""
                    SELECT COUNT(1)
                    FROM asignacion a WITH (UPDLOCK, HOLDLOCK)
                    JOIN dispositivo d ON d.id_dispositivo = a.fk_id_dispositivo
                    JOIN modelo m ON m.id_modelo = d.fk_id_modelo
                    LEFT JOIN reclamo_seguro r ON r.fk_id_asignacion = a.id_asignacion AND r.estado_proceso = 0
                    WHERE a.fk_id_empleado = ?
                      AND (a.fecha_fin_asignacion IS NULL OR a.fecha_fin_asignacion = '')
                      AND m.categoria = ?
                      AND d.estado != 2
                      AND r.id_reclamo IS NULL
                """, (fk_to_empleado, tipo))
                existing = cur.fetchone()[0] or 0
                if existing + inc_count > 1:
                    conflicts.append({'tipo': tipo, 'existing': existing, 'incoming': inc_count})

            if conflicts:
                # Construir mensaje legible
                parts = [f"{c['tipo']} (tiene {c['existing']}, intenta transferir {c['incoming']})" for c in conflicts]
                raise ValueError('Transferencia inválida: el empleado receptor ya tiene dispositivos de tipo(s): ' + ', '.join(parts))

            # No hay conflictos: proceder con la transferencia dentro de una transacción
            self.conn.autocommit = False

            # Obtener asignaciones activas para los dispositivos y el empleado origen
            select_sql = (
                """
                SELECT id_asignacion, fk_id_dispositivo, codigo_plaza
                FROM asignacion
                WHERE fk_id_empleado = ? AND fk_id_dispositivo IN ("""
                + placeholders
                + ") AND (fecha_fin_asignacion IS NULL OR fecha_fin_asignacion = '')"
            )
            params = [fk_from_empleado] + device_ids
            cur.execute(select_sql, params)
            rows = cur.fetchall()

            asign_by_device = { r[1]: {'id_asignacion': r[0], 'codigo_plaza': r[2]} for r in rows }

            # Cerrar las asignaciones activas (fecha_fin_asignacion = GETDATE())
            update_sql = (
                "UPDATE asignacion SET fecha_fin_asignacion = GETDATE() "
                "WHERE fk_id_empleado = ? AND fk_id_dispositivo IN (" + placeholders + ") "
                "AND (fecha_fin_asignacion IS NULL OR fecha_fin_asignacion = '')"
            )
            cur.execute(update_sql, params)

            # Insertar nuevas asignaciones para el empleado receptor (copiar codigo_plaza si existía)
            insert_sql = "INSERT INTO asignacion (fk_id_dispositivo, fk_id_empleado, codigo_plaza, fecha_inicio_asignacion, fecha_creacion) OUTPUT INSERTED.id_asignacion VALUES (?, ?, ?, GETDATE(), GETDATE())"
            for dev_id in device_ids:
                meta = asign_by_device.get(dev_id, {})
                codigo = meta.get('codigo_plaza', '')
                cur.execute(insert_sql, (dev_id, fk_to_empleado, codigo or ''))
                
                # Obtener el ID de la asignación recién creada
                result_row = cur.fetchone()
                if result_row:
                    new_asign_id = int(result_row[0])
                    
                    # Generar correlativo automáticamente
                    if generar_correlativos_para_asignacion:
                        try:
                            # Obtener categoría del dispositivo
                            cur.execute("""
                                SELECT m.categoria
                                FROM dispositivo d
                                JOIN modelo m ON m.id_modelo = d.fk_id_modelo
                                WHERE d.id_dispositivo = ?
                            """, (dev_id,))
                            cat_row = cur.fetchone()
                            if cat_row and cat_row[0]:
                                categoria = cat_row[0]
                                correlativos_dict = generar_correlativos_para_asignacion(self.conn, categoria)
                                if correlativos_dict:
                                    primer_correlativo_completo = list(correlativos_dict.values())[0]
                                    # Extraer solo el número: "PRO-TI-CE-001-000001" -> 1
                                    correlativo_numero = int(primer_correlativo_completo.split('-')[-1])
                                    cur.execute(
                                        "UPDATE asignacion SET correlativo = ? WHERE id_asignacion = ?",
                                        (correlativo_numero, new_asign_id)
                                    )
                        except Exception as e:
                            logger.exception(f'Error generando correlativo en transferencia para asignación {new_asign_id}: {e}')
                            # No detener la transferencia por error en correlativo

            # Optionally, add entries to an audit table or logging view.
            self.conn.commit()
        except Exception as e:
            try:
                self.conn.rollback()
            except:
                pass
            # Propagar error con mensaje legible
            raise Exception(str(e))
        finally:
            try:
                self.conn.autocommit = True
            except:
                pass

    def create_device(
        self,
        fk_id_modelo: int,
        numero_serie: str,
        identificador: str | None = None,
        fecha_obtencion: str | None = None,
        imei: str | None = None,
        imei2: str | None = None,
        direccion_mac: str | None = None,
        ip_asignada: str | None = None,
        tamano: str | None = None,
        color: str | None = None,
        observaciones: str | None = None,
        cargador: bool = False,
        estado: str | None = None,
    ) -> int:
        """Create a device using an existing modelo ID"""
        if not numero_serie:
            raise ValueError("numero_serie es obligatorio")
        if not fk_id_modelo:
            raise ValueError("fk_id_modelo es obligatorio")
        
        cur = self.conn.cursor()
        try:
            # Determine which fecha column exists in the DB (prefer 'fecha_obt' then 'fecha_obtencion')
            fecha_col = None
            if fecha_obtencion is not None:
                if self.has_column('dispositivo', 'fecha_obt'):
                    fecha_col = 'fecha_obt'
                elif self.has_column('dispositivo', 'fecha_obtencion'):
                    fecha_col = 'fecha_obtencion'

            # Build dynamic column list to be tolerant on DB schema variations
            cols = ['numero_serie', 'imei', 'imei2', 'direccion_mac', 'ip_asignada', 'tamano', 'color', 'observaciones']
            vals = [numero_serie, imei, imei2, direccion_mac, ip_asignada, tamano, color, observaciones]
            # identificador column optional support
            if identificador is not None and self.has_column('dispositivo', 'identificador'):
                cols.insert(1, 'identificador')
                vals.insert(1, identificador)
            if fecha_col:
                cols.append(fecha_col)
                vals.append(fecha_obtencion)
            cols.extend(['cargador', 'estado', 'fk_id_modelo'])
            vals.extend([1 if cargador else 0, estado, fk_id_modelo])

            placeholders = ','.join(['?'] * len(cols))
            cols_sql = ', '.join(cols)
            sql = "INSERT INTO dispositivo (" + cols_sql + ") OUTPUT INSERTED.id_dispositivo VALUES (" + placeholders + ")"
            cur.execute(sql, tuple(vals))
            result = cur.fetchone()
            if result is None:
                raise ValueError("No se pudo crear el dispositivo - INSERT no retornó ID")
            new_id = int(result[0])
            self.conn.commit()
            return new_id
        except Exception:
            self.conn.rollback()
            raise

    def create_device_with_brand_model(
        self,
        marca_nombre: str,
        modelo_nombre: str,
        categoria: str,
        numero_serie: str,
        imei: str | None = None,
        imei2: str | None = None,
        direccion_mac: str | None = None,
        ip_asignada: str | None = None,
        tamano: str | None = None,
        color: str | None = None,
        cargador: bool = False,
        estado: str | None = None,
    ) -> int:
        if not numero_serie:
            raise ValueError("numero_serie es obligatorio")
        if not marca_nombre or not modelo_nombre or not categoria:
            raise ValueError("marca_nombre, modelo_nombre y categoria son obligatorios")

        cur = self.conn.cursor()
        try:
            # Transacción manual
            self.conn.autocommit = False
            id_marca = self._get_or_create_marca(marca_nombre)
            id_modelo = self._get_or_create_modelo(modelo_nombre, categoria, id_marca)
            # Build insert dynamically to include optional 'identificador' if present
            cols = ['numero_serie', 'imei', 'imei2', 'direccion_mac', 'ip_asignada',
                    'tamano', 'color', 'observaciones', 'fecha_obtencion', 'cargador', 'estado', 'fk_id_modelo']
            vals = [numero_serie, imei, imei2, direccion_mac, ip_asignada,
                    tamano, color, None, None, 1 if cargador else 0, estado, id_modelo]
            if self.has_column('dispositivo', 'identificador'):
                # keep identificador empty by default for this helper
                cols.insert(1, 'identificador')
                vals.insert(1, None)

            placeholders = ','.join(['?'] * len(cols))
            cols_sql = ', '.join(cols)
            sql = "INSERT INTO dispositivo (" + cols_sql + ") OUTPUT INSERTED.id_dispositivo VALUES (" + placeholders + ")"
            cur.execute(sql, tuple(vals))
            result = cur.fetchone()
            if result is None:
                raise ValueError("No se pudo crear el dispositivo - INSERT no retornó ID")
            new_id = int(result[0])
            self.conn.commit()
            return new_id
        except Exception:
            self.conn.rollback()
            raise
        finally:
            self.conn.autocommit = True

    # CRUD para Marcas
    def list_marcas(self):
        cur = self.conn.cursor()
        # Sólo marcas activas (estado = 1). Por compatibilidad, tratar NULL como activo.
        cur.execute("SELECT id_marca, nombre_marca FROM marca WHERE ISNULL(estado, 1) = 1 ORDER BY nombre_marca")
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def list_marcas_all(self):
        """Devuelve todas las marcas, incluyendo inactivas, con su estado."""
        cur = self.conn.cursor()
        cur.execute("SELECT id_marca, nombre_marca, ISNULL(estado,1) AS estado FROM marca ORDER BY nombre_marca")
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def create_marca(self, nombre_marca: str):
        if not nombre_marca:
            raise ValueError("nombre_marca es obligatorio")
        
        nombre_marca = nombre_marca.strip()
        
        # Validar que no exista con el mismo nombre (case-insensitive)
        cur = self.conn.cursor()
        cur.execute("""
            SELECT id_marca FROM marca 
            WHERE LOWER(nombre_marca) = LOWER(?)
        """, (nombre_marca,))
        
        if cur.fetchone():
            raise ValueError(f"Ya existe una marca con el nombre '{nombre_marca}'")
        
        # Crear la marca
        cur.execute("INSERT INTO marca (nombre_marca, estado) OUTPUT INSERTED.id_marca VALUES (?, ?)", (nombre_marca, 1))
        result = cur.fetchone()
        if result is None:
            raise ValueError("No se pudo crear la marca")
        marca_id = int(result[0])
        self.conn.commit()
        
        return marca_id, nombre_marca

    def update_marca(self, marca_id: int, nombre_marca: str):
        if not nombre_marca:
            raise ValueError("nombre_marca es obligatorio")
        cur = self.conn.cursor()
        cur.execute("UPDATE marca SET nombre_marca = ? WHERE id_marca = ?", (nombre_marca, marca_id))
        self.conn.commit()

    def delete_marca(self, marca_id: int):
        cur = self.conn.cursor()
        # Soft-delete: marcar estado = 0 en lugar de borrar la fila
        cur.execute("UPDATE marca SET estado = 0 WHERE id_marca = ?", (marca_id,))
        self.conn.commit()

    # CRUD para Modelos
    def list_modelos(self, estado: int | None = None, categoria: str | None = None):
        cur = self.conn.cursor()
        # Permitir filtrar por estado y/o categoría si se provee; por defecto devolver solo activos (estado=1)
        base_where = "ISNULL(m.estado, 1) = ? AND ISNULL(ma.estado, 1) = 1"
        params = [estado if estado is not None else 1]
        
        if categoria and str(categoria).strip():
            base_where += " AND m.categoria = ?"
            params.append(str(categoria).strip())
        
        sql = """
            SELECT m.id_modelo, m.nombre_modelo, m.categoria, m.fk_id_marca,
                   ma.nombre_marca, ISNULL(m.estado,1) AS estado,
                   m.salidas, m.capacidad
            FROM modelo m
            LEFT JOIN marca ma ON ma.id_marca = m.fk_id_marca
            WHERE """ + base_where + """
            ORDER BY m.nombre_modelo
        """
        cur.execute(sql, params)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def list_modelos_all(self):
        """Devuelve todos los modelos incluyendo inactivos (para gestión)."""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT m.id_modelo, m.nombre_modelo, m.categoria, m.fk_id_marca,
                   ma.nombre_marca, ISNULL(m.estado,1) AS estado,
                   m.salidas, m.capacidad
            FROM modelo m
            LEFT JOIN marca ma ON ma.id_marca = m.fk_id_marca
            ORDER BY m.nombre_modelo
        """)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def create_modelo(self, nombre_modelo: str, categoria: str, fk_id_marca, estado: int = 1, salidas: int = None, capacidad: str = None):
        if not nombre_modelo or not categoria or not fk_id_marca:
            raise ValueError("nombre_modelo, categoria y fk_id_marca son obligatorios")
        cur = self.conn.cursor()
        # Check duplicate model (same name under same brand) - case insensitive
        cur.execute(
            "SELECT id_modelo FROM modelo WHERE LOWER(nombre_modelo) = LOWER(?) AND fk_id_marca = ?",
            (nombre_modelo.strip(), fk_id_marca)
        )
        if cur.fetchone():
            raise ValueError("Ya existe un modelo con ese nombre para la marca seleccionada")

        cur.execute(
            "INSERT INTO modelo (nombre_modelo, categoria, fk_id_marca, estado, salidas, capacidad) OUTPUT INSERTED.id_modelo VALUES (?, ?, ?, ?, ?, ?)",
            (nombre_modelo.strip(), categoria, fk_id_marca, int(estado), salidas, capacidad)
        )
        result = cur.fetchone()
        if result is None:
            raise ValueError("No se pudo crear el modelo")
        self.conn.commit()
        # Get the ID of the newly created modelo
        return result[0]

    def update_modelo(self, modelo_id: int, nombre_modelo: str, categoria: str, fk_id_marca: int, salidas: int = None, capacidad: str = None):
        if not nombre_modelo or not categoria or not fk_id_marca:
            raise ValueError("nombre_modelo, categoria y fk_id_marca son obligatorios")
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE modelo SET nombre_modelo = ?, categoria = ?, fk_id_marca = ?, salidas = ?, capacidad = ? WHERE id_modelo = ?",
            (nombre_modelo, categoria, fk_id_marca, salidas, capacidad, modelo_id)
        )
        self.conn.commit()

    def delete_modelo(self, modelo_id: int):
        cur = self.conn.cursor()
        # Soft-delete: marcar estado = 0 en lugar de borrar la fila
        cur.execute("UPDATE modelo SET estado = 0 WHERE id_modelo = ?", (modelo_id,))
        self.conn.commit()

    def set_marca_estado(self, marca_id: int, estado: int):
        cur = self.conn.cursor()
        cur.execute("UPDATE marca SET estado = ? WHERE id_marca = ?", (1 if int(estado) else 0, marca_id))
        self.conn.commit()

    def set_modelo_estado(self, modelo_id: int, estado: int):
        cur = self.conn.cursor()
        cur.execute("UPDATE modelo SET estado = ? WHERE id_modelo = ?", (1 if int(estado) else 0, modelo_id))
        self.conn.commit()

    def get_modelo(self, modelo_id: int):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT m.id_modelo, m.nombre_modelo, m.categoria, m.fk_id_marca,
                   ma.nombre_marca, m.salidas, m.capacidad
            FROM modelo m
            LEFT JOIN marca ma ON ma.id_marca = m.fk_id_marca
            WHERE m.id_modelo = ?
        """, (modelo_id,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [c[0] for c in cur.description]
        return dict(zip(cols, row))

    # CRUD para Asignaciones
    def list_asignaciones(self):
        cur = self.conn.cursor()
        cur.execute("""
                 SELECT a.id_asignacion, a.fk_id_dispositivo, a.fk_id_empleado, 
                     a.codigo_plaza, a.fecha_inicio_asignacion, a.fecha_fin_asignacion,
                     a.observaciones, a.correlativo,
                     d.numero_serie, d.imei, m.nombre_modelo, m.categoria
            FROM asignacion a
            JOIN dispositivo d ON d.id_dispositivo = a.fk_id_dispositivo
            LEFT JOIN modelo m ON d.fk_id_modelo = m.id_modelo
            WHERE d.estado != 3
            ORDER BY a.fecha_creacion DESC, a.id_asignacion DESC
        """)
        cols = [c[0] for c in cur.description]
        asignaciones = [dict(zip(cols, r)) for r in cur.fetchall()]
        
        # Agregar nombre del empleado consultando la BD `empleados` primero.
        # Si no existe allí, caemos al mecanismo previo (identity / AuthService) como fallback.
        try:
            # Recolectar ids únicos
            emp_ids = sorted({int(a.get('fk_id_empleado')) for a in asignaciones if a.get('fk_id_empleado')}, key=int)
        except Exception:
            emp_ids = []

        emp_map = {}
        if emp_ids:
            try:
                conn_emp = get_db_empleados()
                cur_emp = conn_emp.cursor()
                # Construir placeholders para pyodbc
                placeholders = ','.join(['?'] * len(emp_ids))
                sql = "SELECT id_empleado, nombre_completo FROM empleados WHERE id_empleado IN (" + placeholders + ")"
                cur_emp.execute(sql, tuple(emp_ids))
                for row in cur_emp.fetchall():
                    try:
                        emp_map[int(row[0])] = str(row[1])
                    except Exception:
                        continue
            except Exception:
                emp_map = {}

        # Rellenar empleado_nombre usando emp_map; si no está, intentar identity/AuthService
        missing_ids = set()
        for a in asignaciones:
            eid = a.get('fk_id_empleado')
            try:
                if eid and int(eid) in emp_map:
                    a['empleado_nombre'] = emp_map.get(int(eid))
                    continue
            except Exception:
                pass
            # marcar para fallback
            a['empleado_nombre'] = None
            if a.get('fk_id_empleado'):
                try:
                    missing_ids.add(int(a.get('fk_id_empleado')))
                except Exception:
                    pass

        if missing_ids:
            try:
                conn_emp = get_db_empleados()
                cur_emp = conn_emp.cursor()
                placeholders = ','.join(['?'] * len(missing_ids))
                sql = "SELECT id_empleado, nombre_completo FROM empleados WHERE id_empleado IN (" + placeholders + ")"
                cur_emp.execute(sql, tuple(missing_ids))
                emp_map2 = {int(r[0]): str(r[1]) for r in cur_emp.fetchall()}
                for a in asignaciones:
                    if not a.get('empleado_nombre') and a.get('fk_id_empleado'):
                        try:
                            eid = int(a.get('fk_id_empleado'))
                            a['empleado_nombre'] = emp_map2.get(eid)
                        except Exception:
                            a['empleado_nombre'] = None
            except Exception:
                pass

        # Final fallback: if still missing, show the numeric id so the UI never muestra vacío
        for a in asignaciones:
            if not a.get('empleado_nombre'):
                a['empleado_nombre'] = a.get('fk_id_empleado')

        # Agregar contador de dispositivos asignados por empleado (solo asignaciones activas)
        try:
            cur.execute("""
                SELECT a.fk_id_empleado, COUNT(*) as cnt
                FROM asignacion a
                JOIN dispositivo d ON d.id_dispositivo = a.fk_id_dispositivo
                WHERE d.estado != 3 AND (a.fecha_fin_asignacion IS NULL OR a.fecha_fin_asignacion = '')
                GROUP BY a.fk_id_empleado
            """)
            counts = {row[0]: row[1] for row in cur.fetchall()}
        except Exception:
            counts = {}

        for a in asignaciones:
            try:
                a['dispositivos_count'] = int(counts.get(a.get('fk_id_empleado')) or 0)
            except Exception:
                a['dispositivos_count'] = 0

        return asignaciones

    def list_active_asignaciones(self):
        """Lista solo las asignaciones activas (sin fecha_fin) y cuyo dispositivo no esté eliminado.
        Usada para seleccionar asignaciones válidas al crear un reclamo.
        """
        cur = self.conn.cursor()
        # Exclude assignments whose device has an active (in-process) reclamo_seguro.
        # We consider a reclamo active if it has no fecha_fin_reclamo or estado_proceso = 0 (En proceso).
        cur.execute("""
            SELECT a.id_asignacion, a.fk_id_dispositivo, a.fk_id_empleado,
                   a.codigo_plaza, a.fecha_inicio_asignacion, a.fecha_fin_asignacion,
                   d.numero_serie, d.imei, m.nombre_modelo, m.categoria, ma.nombre_marca
            FROM asignacion a
            JOIN dispositivo d ON d.id_dispositivo = a.fk_id_dispositivo
            LEFT JOIN modelo m ON d.fk_id_modelo = m.id_modelo
            LEFT JOIN marca ma ON m.fk_id_marca = ma.id_marca
            LEFT JOIN reclamo_seguro r ON r.fk_id_asignacion = a.id_asignacion
                 AND (r.fecha_fin_reclamo IS NULL OR r.estado_proceso = 0)
            WHERE d.estado != 3 AND (a.fecha_fin_asignacion IS NULL OR a.fecha_fin_asignacion = '')
              AND r.id_reclamo IS NULL
            ORDER BY a.id_asignacion DESC
        """)
        cols = [c[0] for c in cur.description]
        asignaciones = [dict(zip(cols, r)) for r in cur.fetchall()]

        # Resolver nombres y empresa de empleados usando la BD `empleados`.
        try:
            emp_ids = sorted({int(a.get('fk_id_empleado')) for a in asignaciones if a.get('fk_id_empleado')}, key=int)
        except Exception:
            emp_ids = []

        emp_name_map = {}
        emp_empresa_map = {}
        if emp_ids:
            try:
                conn_emp = get_db_empleados()
                cur_emp = conn_emp.cursor()
                placeholders = ','.join(['?'] * len(emp_ids))
                sql = "SELECT id_empleado, nombre_completo, empresa FROM empleados WHERE id_empleado IN (" + placeholders + ")"
                cur_emp.execute(sql, tuple(emp_ids))
                for row in cur_emp.fetchall():
                    try:
                        emp_id = int(row[0])
                        emp_name_map[emp_id] = str(row[1]) if row[1] is not None else ''
                        emp_empresa_map[emp_id] = str(row[2]) if row[2] is not None else ''
                    except Exception:
                        continue
            except Exception:
                emp_name_map = {}
                emp_empresa_map = {}

        for a in asignaciones:
            try:
                eid = int(a.get('fk_id_empleado') or 0)
            except Exception:
                eid = None
            if eid and eid in emp_name_map:
                a['empleado_nombre'] = emp_name_map.get(eid)
            else:
                a['empleado_nombre'] = a.get('fk_id_empleado')
            try:
                a['empresa'] = emp_empresa_map.get(eid, '')
            except Exception:
                a['empresa'] = ''

        return asignaciones

    def list_deleted_asignaciones(self):
        """Lista asignaciones cuyo dispositivo fue eliminado (auditoría para admins)"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT a.id_asignacion, a.fk_id_dispositivo, a.fk_id_empleado, 
                   a.codigo_plaza, a.fecha_inicio_asignacion, a.fecha_fin_asignacion,
                   a.observaciones, a.eliminada, a.fecha_eliminacion, a.motivo_eliminacion,
                   d.numero_serie, d.imei, d.estado
            FROM asignacion a
            JOIN dispositivo d ON d.id_dispositivo = a.fk_id_dispositivo
            WHERE a.eliminada = 1 OR d.estado = 3
            ORDER BY a.fecha_eliminacion DESC
        """)
        cols = [c[0] for c in cur.description]
        asignaciones = [dict(zip(cols, r)) for r in cur.fetchall()]
        
        # Agregar nombre del empleado consultando otra BD
        for a in asignaciones:
            a['empleado_nombre'] = self._get_empleado_nombre(a['fk_id_empleado'])
        
        return asignaciones

    def create_asignacion(self, fk_id_dispositivo, fk_id_empleado, codigo_plaza, 
                         fecha_inicio_asignacion, fecha_fin_asignacion=None, observaciones=None, reemplazo=False):
        if not fk_id_dispositivo or not fk_id_empleado:
            raise ValueError("fk_id_dispositivo y fk_id_empleado son obligatorios")

        cur = self.conn.cursor()
        try:
            # Normalizar IDs a enteros
            fk_id_dispositivo = int(fk_id_dispositivo)
            fk_id_empleado = int(fk_id_empleado)

            # Comenzar transacción manualmente para garantizar consistencia
            self.conn.autocommit = False

            # Si existe una asignación activa para este dispositivo, finalizarla con fecha actual
            cur.execute("SELECT id_asignacion FROM asignacion WHERE fk_id_dispositivo = ? AND (fecha_fin_asignacion IS NULL OR fecha_fin_asignacion = '')", (fk_id_dispositivo,))
            row = cur.fetchone()
            if row:
                cur.execute("UPDATE asignacion SET fecha_fin_asignacion = GETDATE() WHERE id_asignacion = ?", (row[0],))

            # Verificar que el empleado no tenga ya una asignación del mismo tipo 
            # Restricciones: 1 Laptop, 1 Celular, 1 Monitor, 1 Mouse, 1 Teclado, 1 Teléfono VoIP
            cur.execute("""
                SELECT m.categoria
                FROM dispositivo d
                JOIN modelo m ON m.id_modelo = d.fk_id_modelo
                WHERE d.id_dispositivo = ?
            """, (fk_id_dispositivo,))
            row_tipo = cur.fetchone()
            tipo_disp = row_tipo[0] if row_tipo else None
            
            # Tipos con restricción de 1 por empleado
            # Añadido 'Tablet' según nueva política: máximo 1 por empleado
            tipos_restringidos = ('Laptop', 'Celular', 'Tablet', 'Monitor', 'Mouse', 'Teclado', 'Telefono VoIP')
            
            if tipo_disp in tipos_restringidos:
                # Contar asignaciones activas del mismo tipo que NO estén en reparación
                # ni tengan un reclamo activo. Si existen, impedir nueva asignación.
                # Usar bloqueo en la selección para evitar race conditions entre checks e inserts.
                cur.execute("""
                    SELECT COUNT(1)
                    FROM asignacion a WITH (UPDLOCK, HOLDLOCK)
                    JOIN dispositivo d ON d.id_dispositivo = a.fk_id_dispositivo
                    JOIN modelo m ON m.id_modelo = d.fk_id_modelo
                    LEFT JOIN reclamo_seguro r ON r.fk_id_asignacion = a.id_asignacion AND r.estado_proceso = 0
                    WHERE a.fk_id_empleado = ?
                      AND (a.fecha_fin_asignacion IS NULL OR a.fecha_fin_asignacion = '')
                      AND m.categoria = ?
                      AND d.estado != 2
                      AND r.id_reclamo IS NULL
                """, (fk_id_empleado, tipo_disp))
                cnt = cur.fetchone()[0] or 0
                if cnt >= 1:
                    raise ValueError(f"El empleado ya tiene asignado un {tipo_disp} (máximo 1).")

            # Insertar nueva asignación. Si es reemplazo, marcarlo en las observaciones para compatibilidad
            obs_final = observaciones or ''
            if reemplazo:
                # Añadir indicador claro para futuras reconciliaciones
                obs_final = (obs_final + ' ').strip() + (' ' if obs_final else '') + 'REEMPLAZO=1'

            cur.execute("""
                INSERT INTO asignacion (
                    fk_id_dispositivo, fk_id_empleado, codigo_plaza,
                    fecha_inicio_asignacion, fecha_fin_asignacion, observaciones
                )
                OUTPUT INSERTED.id_asignacion
                VALUES (?, ?, ?, ?, ?, ?)
            """, (fk_id_dispositivo, fk_id_empleado, codigo_plaza,
                fecha_inicio_asignacion, fecha_fin_asignacion, obs_final))

            # Obtener el id de la asignación recién insertada usando OUTPUT INSERTED
            result = cur.fetchone()
            if not result:
                raise Exception("No se pudo obtener el ID de la asignación creada")
            new_id = int(result[0])

            # Marcar dispositivo como 1 (Asignado)
            cur.execute("UPDATE dispositivo SET estado = ? WHERE id_dispositivo = ?", (1, fk_id_dispositivo))

            # Generar correlativo automáticamente
            if tipo_disp and generar_correlativos_para_asignacion:
                try:
                    correlativos_dict = generar_correlativos_para_asignacion(self.conn, tipo_disp)
                    if correlativos_dict:
                        # Guardar solo el NÚMERO (INT) del primer correlativo
                        primer_correlativo_completo = list(correlativos_dict.values())[0]
                        # Extraer solo el número: "PRO-TI-CE-001-000001" -> 1
                        correlativo_numero = int(primer_correlativo_completo.split('-')[-1])
                        cur.execute(
                            "UPDATE asignacion SET correlativo = ? WHERE id_asignacion = ?",
                            (correlativo_numero, new_id)
                        )
                    else:
                        logger.warning(f'No se pudo generar correlativo para asignación {new_id} (categoría: {tipo_disp})')
                except Exception as e:
                    logger.exception(f'Error generando correlativo para asignación {new_id}: {e}')
                    raise Exception(f'Error generando correlativo: {str(e)}')
            else:
                logger.warning(f'No se generó correlativo para asignación {new_id} (categoría: {tipo_disp}, helper disponible: {generar_correlativos_para_asignacion is not None})')

            self.conn.commit()
            return new_id
        except Exception:
            self.conn.rollback()
            raise
        finally:
            self.conn.autocommit = True

    def update_asignacion_end_date(self, asignacion_id: int, fecha_fin_asignacion):
        cur = self.conn.cursor()
        # If setting a fecha_fin, update the device estado to 0 (Sin asignar)
        if fecha_fin_asignacion:
            # Get the device id from the assignment
            cur.execute("SELECT fk_id_dispositivo FROM asignacion WHERE id_asignacion = ?", (asignacion_id,))
            row = cur.fetchone()
            if row:
                device_id = row[0]
                # Update device estado to 0 (Sin asignar)
                cur.execute("UPDATE dispositivo SET estado = ? WHERE id_dispositivo = ?", (0, device_id))
        
        # Update the assignment end date
        cur.execute(
            "UPDATE asignacion SET fecha_fin_asignacion = ? WHERE id_asignacion = ?",
            (fecha_fin_asignacion, asignacion_id)
        )
        self.conn.commit()

    def delete_asignacion(self, asignacion_id: int):
        cur = self.conn.cursor()
        # Comprobar si existen reclamos asociados a la asignación
        cur.execute("SELECT COUNT(1) FROM reclamo_seguro WHERE fk_id_asignacion = ?", (asignacion_id,))
        row = cur.fetchone()
        if row and row[0] > 0:
            raise ValueError("No se puede eliminar la asignación: existen reclamos asociados. Elimine primero los reclamos.")
        # Obtener el dispositivo asociado (si existe) y marcarlo como sin asignar
        cur.execute("SELECT fk_id_dispositivo FROM asignacion WHERE id_asignacion = ?", (asignacion_id,))
        r = cur.fetchone()
        try:
            if r and r[0]:
                device_id = r[0]
                cur.execute("UPDATE dispositivo SET estado = ? WHERE id_dispositivo = ?", (ESTADO_SIN_ASIGNAR, device_id))
        except Exception:
            # no bloquear la eliminación por fallo al marcar estado, pero reportar luego si es necesario
            pass

        cur.execute("DELETE FROM asignacion WHERE id_asignacion = ?", (asignacion_id,))
        self.conn.commit()

    # CRUD para Reclamos
    def list_reclamos(self):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT r.id_reclamo, r.fk_id_asignacion, r.fecha_incidencia, r.lugar_incidencia,
                   r.fecha_inicio_reclamo, r.lugar_reclamo, r.estado_proceso, r.fecha_fin_reclamo,
                   a.fk_id_empleado,
                   d.numero_serie, d.imei,
                   m.nombre_modelo, ma.nombre_marca
            FROM reclamo_seguro r
            JOIN asignacion a ON a.id_asignacion = r.fk_id_asignacion
            JOIN dispositivo d ON d.id_dispositivo = a.fk_id_dispositivo
            LEFT JOIN modelo m ON d.fk_id_modelo = m.id_modelo
            LEFT JOIN marca ma ON m.fk_id_marca = ma.id_marca
            WHERE d.estado != 3
            ORDER BY r.estado_proceso ASC, r.id_reclamo DESC
        """)
        cols = [c[0] for c in cur.description]
        reclamos = [dict(zip(cols, r)) for r in cur.fetchall()]

        # Resolver nombres de empleados y empresa: intentar lookup individual y completar en lote si faltan
        missing_ids = set()
        for r in reclamos:
            if r.get('fk_id_empleado'):
                try:
                    missing_ids.add(int(r.get('fk_id_empleado')))
                except Exception:
                    pass
            try:
                name = self._get_empleado_nombre(r.get('fk_id_empleado'))
            except Exception:
                name = None
            if name:
                r['empleado_nombre'] = name
            else:
                r['empleado_nombre'] = None

        if missing_ids:
            try:
                conn_emp = get_db_empleados()
                cur_emp = conn_emp.cursor()
                placeholders = ','.join(['?'] * len(missing_ids))
                sql = "SELECT id_empleado, nombre_completo, empresa FROM empleados WHERE id_empleado IN (" + placeholders + ")"
                cur_emp.execute(sql, tuple(missing_ids))
                emp_map = {}
                emp_company = {}
                for row in cur_emp.fetchall():
                    try:
                        emp_id = int(row[0])
                        emp_map[emp_id] = str(row[1]) if row[1] is not None else None
                        emp_company[emp_id] = str(row[2]) if row[2] is not None else ''
                    except Exception:
                        continue
                for r in reclamos:
                    if not r.get('empleado_nombre') and r.get('fk_id_empleado'):
                        try:
                            eid = int(r.get('fk_id_empleado'))
                            r['empleado_nombre'] = emp_map.get(eid)
                        except Exception:
                            r['empleado_nombre'] = None
                    try:
                        fk = r.get('fk_id_empleado')
                        r['empresa'] = emp_company.get(int(fk)) if fk and int(fk) in emp_company else ''
                    except Exception:
                        r['empresa'] = ''
            except Exception:
                pass

        # Fallback final: usar id numérico si no se pudo resolver el nombre
        for r in reclamos:
            if not r.get('empleado_nombre'):
                r['empleado_nombre'] = r.get('fk_id_empleado')
            # Ensure empresa field exists (try to resolve via AuthService if possible)
            if 'empresa' not in r:
                r['empresa'] = ''

        return reclamos

    def get_reclamo(self, reclamo_id: int):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT r.id_reclamo, r.fk_id_asignacion, r.fecha_incidencia, r.lugar_incidencia,
                   r.fecha_inicio_reclamo, r.lugar_reclamo, r.estado_proceso, r.fecha_fin_reclamo,
                   a.fk_id_empleado,
                   d.numero_serie, d.imei,
                   m.nombre_modelo, ma.nombre_marca
            FROM reclamo_seguro r
            JOIN asignacion a ON a.id_asignacion = r.fk_id_asignacion
            JOIN dispositivo d ON d.id_dispositivo = a.fk_id_dispositivo
            LEFT JOIN modelo m ON d.fk_id_modelo = m.id_modelo
            LEFT JOIN marca ma ON m.fk_id_marca = ma.id_marca
            WHERE r.id_reclamo = ? AND d.estado != 3
        """, (reclamo_id,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [c[0] for c in cur.description]
        recl = dict(zip(cols, row))
        # Resolver nombre del empleado con fallback a AuthService y finalmente al id
        try:
            name = self._get_empleado_nombre(recl.get('fk_id_empleado'))
        except Exception:
            name = None
        if name:
            recl['empleado_nombre'] = name
        else:
            try:
                fk = recl.get('fk_id_empleado')
                if fk:
                    conn_emp = get_db_empleados()
                    cur_emp = conn_emp.cursor()
                    cur_emp.execute("SELECT nombre_completo, empresa FROM empleados WHERE id_empleado = ?", (int(fk),))
                    rrow = cur_emp.fetchone()
                    if rrow:
                        recl['empleado_nombre'] = rrow[0]
                        recl['empresa'] = rrow[1] if rrow[1] is not None else ''
                    else:
                        recl['empleado_nombre'] = recl.get('fk_id_empleado')
                        recl['empresa'] = ''
                else:
                    recl['empleado_nombre'] = recl.get('fk_id_empleado')
                    recl['empresa'] = ''
            except Exception:
                recl['empleado_nombre'] = recl.get('fk_id_empleado')
                recl['empresa'] = ''

        # Ensure empresa exists if not set above
        if 'empresa' not in recl:
            recl['empresa'] = ''

        return recl

    def create_reclamo(self, fk_id_asignacion, fecha_incidencia, lugar_incidencia,
                      fecha_inicio_reclamo, lugar_reclamo, estado_proceso, fecha_fin_reclamo=None,
                      img_evidencia=None, img_form=None):
        # Fecha y lugar de la incidencia son opcionales. Requerimos al menos la asignación
        # y la fecha de inicio del reclamo (fecha_inicio_reclamo) para continuar.
        if not fk_id_asignacion or not fecha_inicio_reclamo:
            raise ValueError("fk_id_asignacion y fecha_inicio_reclamo son obligatorios")
        # Validar que la asignación exista; no crear una nueva asignación desde aquí
        asign = self.get_asignacion(int(fk_id_asignacion))
        if not asign:
            raise ValueError(f"Asignación {fk_id_asignacion} no encontrada")

        # Normalizar estado a entero 0/1
        try:
            estado_val = 1 if str(estado_proceso) in ('1', 'true', 'True') or estado_proceso is True else 0
        except:
            estado_val = 0

        cur = self.conn.cursor()
        # Si el reclamo ya viene marcado como completado y no se pasó fecha_fin,
        # insertar usando la fecha/hora actual del servidor (GETDATE()).
        # Insertar los nuevos campos `fecha_incidencia` y `lugar_incidencia`.
        if estado_val and (not fecha_fin_reclamo):
            cur.execute("""
                INSERT INTO reclamo_seguro (
                    fk_id_asignacion, fecha_incidencia, lugar_incidencia,
                    fecha_inicio_reclamo, lugar_reclamo, estado_proceso, fecha_fin_reclamo,
                    img_evidencia, img_form
                ) VALUES (?, ?, ?, ?, ?, ?, GETDATE(), ?, ?)
            """, (fk_id_asignacion, fecha_incidencia, lugar_incidencia,
                fecha_inicio_reclamo, lugar_reclamo, estado_val, img_evidencia, img_form))
        else:
            cur.execute("""
                INSERT INTO reclamo_seguro (
                    fk_id_asignacion, fecha_incidencia, lugar_incidencia,
                    fecha_inicio_reclamo, lugar_reclamo, estado_proceso, fecha_fin_reclamo,
                    img_evidencia, img_form
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (fk_id_asignacion, fecha_incidencia, lugar_incidencia,
                fecha_inicio_reclamo, lugar_reclamo, estado_val, fecha_fin_reclamo, img_evidencia, img_form))

        # Después de insertar el reclamo, actualizar el estado del dispositivo asociado a "En reparacion" (2)
        try:
            # Obtener el dispositivo asociado a la asignación
            cur.execute("SELECT fk_id_dispositivo FROM asignacion WHERE id_asignacion = ?", (fk_id_asignacion,))
            row = cur.fetchone()
            if row and row[0]:
                device_id = row[0]
                cur.execute("UPDATE dispositivo SET estado = ? WHERE id_dispositivo = ?", (2, device_id))
        except Exception:
            # Si falla la actualización del estado del dispositivo, revertimos para mantener consistencia
            self.conn.rollback()
            raise

        self.conn.commit()

    def get_asignacion(self, asignacion_id: int):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT a.id_asignacion, a.fk_id_dispositivo, a.fk_id_empleado,
                   a.codigo_plaza, a.fecha_inicio_asignacion, a.fecha_fin_asignacion, a.observaciones,
                   a.estado_documentacion, a.correlativo,
                   d.numero_serie, d.imei,
                   m.nombre_modelo, ma.nombre_marca, m.categoria,
                   p.numero_linea, p.costo_plan, p.moneda_plan,
                   p.fecha_inicio AS plan_fecha_inicio, p.fecha_fin AS plan_fecha_fin
            FROM asignacion a
            JOIN dispositivo d ON d.id_dispositivo = a.fk_id_dispositivo
            LEFT JOIN modelo m ON m.id_modelo = d.fk_id_modelo
            LEFT JOIN marca ma ON ma.id_marca = m.fk_id_marca
            LEFT JOIN planes p ON p.id_plan = d.fk_id_plan
            WHERE a.id_asignacion = ? AND d.estado != 3
        """, (asignacion_id,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [c[0] for c in cur.description]
        asign = dict(zip(cols, row))
        # Resolver nombre del empleado, con intento adicional contra AuthService si es necesario
        try:
            name = self._get_empleado_nombre(asign.get('fk_id_empleado'))
        except Exception:
            name = None
        if name:
            asign['empleado_nombre'] = name
        else:
            try:
                fk = asign.get('fk_id_empleado')
                if fk:
                    conn_emp = get_db_empleados()
                    cur_emp = conn_emp.cursor()
                    cur_emp.execute("SELECT nombre_completo FROM empleados WHERE id_empleado = ?", (int(fk),))
                    rrow = cur_emp.fetchone()
                    if rrow and rrow[0]:
                        asign['empleado_nombre'] = rrow[0]
                    else:
                        asign['empleado_nombre'] = asign.get('fk_id_empleado')
                else:
                    asign['empleado_nombre'] = asign.get('fk_id_empleado')
            except Exception:
                asign['empleado_nombre'] = asign.get('fk_id_empleado')
        return asign

    def record_download(self, asignacion_id: int) -> bool:
        """Incrementa el contador de descargas y actualiza la marca de tiempo (second precision).

        Si las columnas no existen, intenta crearlas (para entornos sin migración aplicada).
        Retorna True si la operación fue exitosa, False en caso de error.
        """
        cur = self.conn.cursor()
        try:
            # Asegurar columnas (crearlas si no existen)
            if not self.has_column('asignacion', 'descargas'):
                try:
                    cur.execute("ALTER TABLE asignacion ADD descargas INT NULL CONSTRAINT DF_asignacion_descargas DEFAULT (0)")
                except Exception:
                    # ignore if concurrent or unsupported
                    pass
            if not self.has_column('asignacion', 'ultima_descarga'):
                try:
                    cur.execute("ALTER TABLE asignacion ADD ultima_descarga DATETIME NULL")
                except Exception:
                    pass

            # Ejecutar actualización: incrementar contador y fijar timestamp a GETDATE() (SQL Server)
            cur.execute("UPDATE asignacion SET descargas = ISNULL(descargas,0) + 1, ultima_descarga = GETDATE() WHERE id_asignacion = ?", (asignacion_id,))
            self.conn.commit()
            return True
        except Exception:
            try:
                self.conn.rollback()
            except Exception:
                pass
            return False

    def update_reclamo(self, reclamo_id: int, estado_proceso=None, fecha_fin_reclamo=None, lugar_reclamo=None,
                      img_evidencia=None, img_form=None, remove_img_evidencia=False, remove_img_form=False,
                      fecha_robo=None, fecha_inicio_reclamo=None):
        cur = self.conn.cursor()
        # Normalizar estado a entero 0/1
        try:
            estado_val = 1 if str(estado_proceso) in ('1', 'true', 'True') or estado_proceso is True else 0
        except:
            estado_val = 0

        # Construir la consulta dinámicamente según qué campos se actualicen
        updates = []
        params = []
        
        updates.append("estado_proceso = ?")
        params.append(estado_val)
        
        # img_evidencia handling: if a new file is provided, use it; else if remove flag set, set to NULL
        if img_evidencia is not None:
            updates.append("img_evidencia = ?")
            params.append(img_evidencia)
        elif remove_img_evidencia:
            updates.append("img_evidencia = ?")
            params.append(None)
        
        if img_form is not None:
            updates.append("img_form = ?")
            params.append(img_form)
        elif remove_img_form:
            updates.append("img_form = ?")
            params.append(None)

        # lugar_reclamo can be explicitly set to None to clear it; use provided value
        updates.append("lugar_reclamo = ?")
        params.append(lugar_reclamo)

        # fecha_robo (fecha de la incidencia) and fecha_inicio_reclamo: update only if provided (not None)
        from datetime import datetime
        try:
            if fecha_robo is not None:
                # normalize empty string to NULL
                if fecha_robo == '':
                    updates.append("fecha_incidencia = ?")
                    params.append(None)
                else:
                    # validate not future date
                    try:
                        fr = datetime.fromisoformat(fecha_robo).date()
                        if fr > datetime.now().date():
                            raise ValueError('fecha_incidencia no puede ser futura')
                    except ValueError:
                        # re-raise with clear message
                        raise ValueError('Formato de fecha_incidencia inválido o fecha futura')
                    updates.append("fecha_incidencia = ?")
                    params.append(str(fr))

            if fecha_inicio_reclamo is not None:
                if fecha_inicio_reclamo == '':
                    updates.append("fecha_inicio_reclamo = ?")
                    params.append(None)
                else:
                    try:
                        fi = datetime.fromisoformat(fecha_inicio_reclamo).date()
                        if fi > datetime.now().date():
                            raise ValueError('fecha_inicio_reclamo no puede ser futura')
                    except ValueError:
                        raise ValueError('Formato de fecha_inicio_reclamo inválido o fecha futura')
                    updates.append("fecha_inicio_reclamo = ?")
                    params.append(str(fi))
        except ValueError:
            # Bubble up validation errors to the caller for proper HTTP 400
            raise
        
        # Si se marca como completado y no se provee fecha_fin_reclamo, usar GETDATE().
        if estado_val and (not fecha_fin_reclamo):
            set_clause = ', '.join(updates)
            query = "UPDATE reclamo_seguro SET " + set_clause + ", fecha_fin_reclamo = GETDATE() WHERE id_reclamo = ?"
            cur.execute(query, params + [reclamo_id])
        else:
            updates.append("fecha_fin_reclamo = ?")
            params.append(fecha_fin_reclamo)
            set_clause = ', '.join(updates)
            query = "UPDATE reclamo_seguro SET " + set_clause + " WHERE id_reclamo = ?"
            cur.execute(query, params + [reclamo_id])

        # Si el reclamo se marca como completado (estado_proceso = 1), volver a poner el dispositivo como 'Asignado' (1)
        # siempre y cuando exista una asignación vinculada y el dispositivo no esté eliminado.
        if estado_val:
            try:
                # Obtener fk_id_asignacion para este reclamo
                cur.execute("SELECT fk_id_asignacion FROM reclamo_seguro WHERE id_reclamo = ?", (reclamo_id,))
                row = cur.fetchone()
                if row and row[0]:
                    fk_asig = row[0]
                    cur.execute("SELECT fk_id_dispositivo FROM asignacion WHERE id_asignacion = ?", (fk_asig,))
                    r2 = cur.fetchone()
                    if r2 and r2[0]:
                        device_id = r2[0]
                        # Asegurarse de que el dispositivo no esté eliminado (estado != 3)
                        cur.execute("SELECT estado FROM dispositivo WHERE id_dispositivo = ?", (device_id,))
                        st = cur.fetchone()
                        if st and st[0] != 3:
                            cur.execute("UPDATE dispositivo SET estado = ? WHERE id_dispositivo = ?", (1, device_id))
            except Exception:
                # En caso de error al restaurar estado del dispositivo, revertimos la transacción
                self.conn.rollback()
                raise

        self.conn.commit()

    def delete_reclamo(self, reclamo_id: int):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM reclamo_seguro WHERE id_reclamo = ?", (reclamo_id,))
        self.conn.commit()

    # =============================================
    # MÉTODOS DE EDICIÓN Y AUDITORÍA
    # =============================================

    def update_device(self, device_id: int, **kwargs):
        """Actualiza un dispositivo y registra en auditoría"""
        try:
            cur = self.conn.cursor()
            
            # Obtener datos anteriores
            device_anterior = self.get_device(device_id)
            if not device_anterior:
                raise ValueError("Dispositivo no encontrado")
            
            # Construir UPDATE dinámico (no incluir campos que no existen en la tabla)
            allowed_fields = ['numero_serie', 'identificador', 'imei', 'imei2', 'direccion_mac',
                              'ip_asignada', 'tamano', 'color', 'cargador', 'estado', 'fk_id_modelo', 'observaciones', 'fecha_obtencion', 'fecha_obt']
            
            # Handle fecha_obt/fecha_obtencion schema-aware: normalize to actual column name
            normalized_kwargs = dict(kwargs)
            if 'fecha_obt' in normalized_kwargs or 'fecha_obtencion' in normalized_kwargs:
                # Get the actual column name that exists in DB
                fecha_value = normalized_kwargs.pop('fecha_obt', None) or normalized_kwargs.pop('fecha_obtencion', None)
                if fecha_value is not None:
                    # Prefer new column name 'fecha_obt', fallback to legacy 'fecha_obtencion'
                    if self.has_column('dispositivo', 'fecha_obt'):
                        normalized_kwargs['fecha_obt'] = fecha_value
                    elif self.has_column('dispositivo', 'fecha_obtencion'):
                        normalized_kwargs['fecha_obtencion'] = fecha_value
                    # If neither column exists, silently ignore the value
            
            # Bracket-quote each column name: identifiers are from the allowed_fields whitelist
            # but quoting prevents any edge-case injection if the list were ever extended.
            set_clause = ', '.join(['[' + k + '] = ?' for k in normalized_kwargs.keys() if k in allowed_fields])
            values = [v for k, v in normalized_kwargs.items() if k in allowed_fields]
            
            if not set_clause:
                raise ValueError("No hay campos válidos para actualizar")
            
            values.append(device_id)
            
            query = "UPDATE dispositivo SET " + set_clause + " WHERE id_dispositivo = ?"
            cur.execute(query, values)
            
            self.conn.commit()
            
            # Registrar en auditoría (aquí iría sp_RegistrarAuditoria si es necesario)
            return True
            
        except Exception as e:
            self.conn.rollback()
            raise Exception(f"Error actualizando dispositivo: {str(e)}")

    def get_active_asignacion_by_device(self, device_id: int):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT id_asignacion, fk_id_dispositivo, fk_id_empleado, codigo_plaza,
                   fecha_inicio_asignacion, fecha_fin_asignacion, observaciones
            FROM asignacion
            WHERE fk_id_dispositivo = ? AND (fecha_fin_asignacion IS NULL OR fecha_fin_asignacion = '')
              AND fk_id_dispositivo IN (SELECT id_dispositivo FROM dispositivo WHERE estado != 3)
        """, (device_id,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [c[0] for c in cur.description]
        asign = dict(zip(cols, row))
        asign['empleado_nombre'] = self._get_empleado_nombre(asign.get('fk_id_empleado'))
        return asign

    def finalize_assignment_by_device(self, device_id: int, fecha_fin=None, commit: bool = True):
        """Marca la asignación activa del dispositivo como finalizada.
        Si `commit` es False, no hace commit (útil para llamar desde flujos transaccionales).
        Devuelve la `fecha_fin` (datetime) si se realizó, o `None` si no existía asignación activa."""
        try:
            cur = self.conn.cursor()
            # Buscar asignación activa (solo en dispositivos no eliminados)
            cur.execute("""
                SELECT id_asignacion FROM asignacion 
                WHERE fk_id_dispositivo = ? AND (fecha_fin_asignacion IS NULL OR fecha_fin_asignacion = '')
                  AND fk_id_dispositivo IN (SELECT id_dispositivo FROM dispositivo WHERE estado != 3)
            """, (device_id,))
            row = cur.fetchone()
            if not row:
                return None
            asign_id = row[0]
            # Usar fecha actual si no se provee
            if not fecha_fin:
                cur.execute("SELECT GETDATE()")
                fecha_fin = cur.fetchone()[0]

            # Actualizar asignación
            cur.execute("UPDATE asignacion SET fecha_fin_asignacion = ? WHERE id_asignacion = ?", (fecha_fin, asign_id))
            # Actualizar estado del dispositivo a 0 (Sin asignar)
            cur.execute("UPDATE dispositivo SET estado = ? WHERE id_dispositivo = ?", (0, device_id))
            if commit:
                self.conn.commit()
            return fecha_fin
        except Exception:
            try:
                if commit:
                    self.conn.rollback()
            except:
                pass
            raise

    def backup_and_delete_device(self, device_id: int, motivo_baja: str = None, usuario_id: int = None):
        """Realiza soft delete de un dispositivo (marca estado como 3 - Eliminado sin borrar de la tabla)
        También registra en auditoría las asignaciones asociadas"""
        try:
            cur = self.conn.cursor()
            self.conn.autocommit = False
            
            # Obtener datos del dispositivo
            device = self.get_device(device_id)
            if not device:
                raise ValueError("Dispositivo no encontrado")
            
            # NOTE: No modificar tablas que no existen en el esquema.
            # Solo concatenar el motivo (si existe) a observaciones y marcar estado=3.
            # (Anteriormente intentábamos actualizar una columna `eliminada` en asignacion,
            #  que no existe en este esquema y provocaba errores SQL.)

            # Si se proporcionó un motivo, concatenarlo a las observaciones existentes
            if motivo_baja:
                # Evitar duplicar el mismo motivo si ya fue agregado previamente.
                try:
                    cur2 = self.conn.cursor()
                    cur2.execute("SELECT observaciones FROM dispositivo WHERE id_dispositivo = ?", (device_id,))
                    row_obs = cur2.fetchone()
                    existing_obs = row_obs[0] if row_obs and row_obs[0] is not None else ''
                except Exception:
                    existing_obs = ''

                motivo_norm = (motivo_baja or '').strip()
                # Si el motivo ya aparece en las observaciones (ignorar mayúsculas/minúsculas), no lo duplicamos
                if motivo_norm and motivo_norm.lower() not in (existing_obs or '').lower():
                    # Evitar truncamiento: consultar longitud máxima de la columna
                    try:
                        cur3 = self.conn.cursor()
                        cur3.execute("""
                            SELECT CHARACTER_MAXIMUM_LENGTH
                            FROM INFORMATION_SCHEMA.COLUMNS
                            WHERE TABLE_NAME = 'dispositivo' AND COLUMN_NAME = 'observaciones'
                        """)
                        row = cur3.fetchone()
                        maxlen = row[0] if row and row[0] is not None else None
                    except Exception:
                        maxlen = None

                    combined_marker = ' | Motivo baja: ' + motivo_norm
                    try:
                        effective_max = 100
                        if isinstance(maxlen, int) and maxlen > 0 and maxlen < 100:
                            effective_max = int(maxlen)
                    except Exception:
                        effective_max = 100

                    # Usar LEFT para evitar excepciones por truncamiento
                    cur.execute("""
                        UPDATE dispositivo
                        SET observaciones = LEFT(ISNULL(observaciones, '') + ?, ?)
                        WHERE id_dispositivo = ?
                    """, (combined_marker, int(effective_max), device_id))

            # La gestión de printer_config.json se maneja mediante update_printer_config_state en routes.py

            # Marcar dispositivo como eliminado (soft delete) - estado 3
            cur.execute("""
                UPDATE dispositivo 
                SET estado = ?
                WHERE id_dispositivo = ?
            """, (3, device_id))
            # Intentar marcar también todos los componentes asociados como eliminados (estado=3)
            try:
                cur.execute("UPDATE componente SET estado = ? WHERE fk_id_dispositivo = ?", (3, device_id))
            except Exception:
                # Si la columna/tabla no existe o falla, no abortamos el proceso de eliminación del dispositivo
                logger.exception('No se pudo marcar componentes como eliminados para dispositivo %s', device_id)
            
            self.conn.commit()
            return True
            
        except Exception as e:
            self.conn.rollback()
            raise Exception(f"Error eliminando dispositivo: {str(e)}")
        finally:
            self.conn.autocommit = True

    def list_deleted_devices(self):
        """Lista dispositivos eliminados (ordenados por los más recientes primero)"""
        cur = self.conn.cursor()
        # Note: include marca name to display in UI
        # Ordena por id_dispositivo DESC para mostrar los más recientes primero
        cur.execute("""
            SELECT d.id_dispositivo, d.numero_serie, d.identificador, d.imei, d.imei2, d.direccion_mac,
                   d.ip_asignada, d.tamano, d.color, d.cargador, d.observaciones, d.estado,
                   d.fk_id_modelo,
                   m.nombre_modelo, m.categoria, ma.nombre_marca
            FROM dispositivo d
            LEFT JOIN modelo m ON m.id_modelo = d.fk_id_modelo
            LEFT JOIN marca ma ON ma.id_marca = m.fk_id_marca
            WHERE d.estado = 3
            ORDER BY d.id_dispositivo DESC
        """)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def restore_deleted_device(self, device_id: int):
        """Restaura un dispositivo eliminado (soft delete)"""
        try:
            cur = self.conn.cursor()
            self.conn.autocommit = False

            # Verificar que el dispositivo exista y esté eliminado
            cur.execute("SELECT id_dispositivo, ip_asignada FROM dispositivo WHERE id_dispositivo = ? AND estado = 3", (device_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError("Dispositivo no encontrado o no está eliminado")

            ip_asignada = row[1] if len(row) > 1 else None

            # Restaurar a "Sin asignar" (0) por defecto
            # La gestión de printer_config.json se maneja mediante update_printer_config_state en routes.py
            new_estado = 0

            cur.execute("""
                UPDATE dispositivo
                SET estado = ?
                WHERE id_dispositivo = ?
            """, (new_estado, device_id))

            self.conn.commit()
            return True

        except Exception as e:
            self.conn.rollback()
            raise Exception(f"Error restaurando dispositivo: {str(e)}")
        finally:
            self.conn.autocommit = True

    def list_celulares(self):
        """Lista todos los celulares activos (no eliminados) con información de empleado asignado"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT d.id_dispositivo, d.identificador, d.imei, d.numero_serie, d.observaciones, 
                   ISNULL(d.estado, 0) as estado,
                   m.nombre_modelo, m.categoria, ma.nombre_marca,
                   a.fk_id_empleado,
                   p.numero_linea
            FROM dispositivo d
            JOIN modelo m ON m.id_modelo = d.fk_id_modelo
            LEFT JOIN marca ma ON ma.id_marca = m.fk_id_marca
            LEFT JOIN asignacion a ON a.fk_id_dispositivo = d.id_dispositivo 
                AND (a.fecha_fin_asignacion IS NULL OR a.fecha_fin_asignacion = '')
            LEFT JOIN planes p ON p.id_plan = d.fk_id_plan
            WHERE m.categoria = 'Celular' 
              AND d.estado != 3
            ORDER BY d.id_dispositivo DESC
        """)
        cols = [c[0] for c in cur.description]
        devices = [dict(zip(cols, r)) for r in cur.fetchall()]
        
        # Obtener nombres de empleados desde la BD externa
        empleado_ids = [d['fk_id_empleado'] for d in devices if d.get('fk_id_empleado')]
        empleados_map = {}
        
        if empleado_ids:
            try:
                conn_emp = get_db_empleados()
                cur_emp = conn_emp.cursor()
                placeholders = ','.join('?' * len(empleado_ids))
                sql = "SELECT id_empleado, nombre_completo FROM empleados WHERE id_empleado IN (" + placeholders + ")"
                cur_emp.execute(sql, empleado_ids)
                for row in cur_emp.fetchall():
                    empleados_map[row[0]] = row[1]
            except Exception as e:
                logger.warning(f"Error obteniendo nombres de empleados para celulares: {e}")
        
        # Agregar nombre_completo a cada dispositivo
        for d in devices:
            emp_id = d.get('fk_id_empleado')
            d['nombre_completo'] = empleados_map.get(emp_id, '') if emp_id else ''
        
        return devices

    def list_backups(self, recuperables_only: bool = True):
        """Lista dispositivos en respaldo disponibles para recuperación"""
        cur = self.conn.cursor()
        query = """
            SELECT IdRespaldo, IdDispositivo, NumeroSerie, Imei, Estado, 
                   FechaEliminacion, MotivoBaja, Recuperable
            FROM RespaldoDispositivos
        """
        if recuperables_only:
            query += " WHERE Recuperable = 1"
        query += " ORDER BY FechaEliminacion DESC"
        
        cur.execute(query)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def restore_device(self, backup_id: int, usuario_id: int = None):
        """Restaura un dispositivo desde respaldo"""
        try:
            cur = self.conn.cursor()
            self.conn.autocommit = False
            
            # Ejecutar stored procedure de restauración
            cur.execute("""
                EXEC sp_RestaurarDispositivo
                    @IdRespaldo = ?,
                    @UsuarioRestauracion = ?
            """, backup_id, usuario_id)
            
            self.conn.commit()
            return True
            
        except Exception as e:
            self.conn.rollback()
            raise Exception(f"Error restaurando dispositivo: {str(e)}")
        finally:
            self.conn.autocommit = True

    def get_auditoria_reciente(self, tabla: str = None, dias: int = 30):
        """Obtiene registro de auditoría reciente"""
        cur = self.conn.cursor()
        query = """
            SELECT IdAuditoria, TablaPrincipal, TipoOperacion, IdRegistro,
                   UsuarioId, FechaOperacion, Observaciones
            FROM vw_AuditoriaReciente
            WHERE FechaOperacion >= DATEADD(day, -?, GETDATE())
        """
        params = [int(dias) if dias is not None else 30]
        if tabla:
            query += " AND TablaPrincipal = ?"
            params.append(tabla)
        query += " ORDER BY FechaOperacion DESC"

        cur.execute(query, params)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def get_dispositivos_empleado(self, fk_id_empleado):
        """Obtiene todos los dispositivos asignados activos de un empleado"""
        cur = self.conn.cursor()
        cur.execute("""
                        SELECT DISTINCT d.id_dispositivo, d.numero_serie, d.identificador, d.imei, ISNULL(d.estado,0) as estado,
                                     m.categoria, m.nombre_modelo, ma.nombre_marca, a.fecha_inicio_asignacion
            FROM asignacion a
            JOIN dispositivo d ON d.id_dispositivo = a.fk_id_dispositivo
            LEFT JOIN modelo m ON d.fk_id_modelo = m.id_modelo
            LEFT JOIN marca ma ON ma.id_marca = m.fk_id_marca
            WHERE a.fk_id_empleado = ? 
              AND a.fecha_fin_asignacion IS NULL
              AND d.estado != 3
            ORDER BY m.categoria, d.numero_serie
        """, (fk_id_empleado,))
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def get_empleado(self, empleado_id: int):
        """Obtiene datos de un empleado por ID desde la BD de identidad o empleados
        
        Retorna dict con campos:
        - id_empleado / IdEmpleado
        - nombre_completo / NombreCompleto
        - empresa
        - puesto
        - departamento
        - sucursal
        - pasaporte
        """
        if not empleado_id:
            return None

        try:
            conn_emp = get_db_empleados()
            cur = conn_emp.cursor()
            # Seleccionar columnas que existen en el esquema de `empleados`
            cur.execute("""
                SELECT id_empleado, codigo_empleado, nombre_completo, empresa, puesto, pasaporte,
                       departamento, sucursal, estado
                FROM empleados 
                WHERE id_empleado = ?
            """, (empleado_id,))
            row = cur.fetchone()
            if row:
                cols = [c[0] for c in cur.description]
                result = dict(zip(cols, row))
                # Normalizar claves a nombres que usa el resto del código
                if 'NombreCompleto' in result and 'nombre_completo' not in result:
                    result['nombre_completo'] = result.get('NombreCompleto')
                if 'IdEmpleado' in result and 'id_empleado' not in result:
                    result['id_empleado'] = result.get('IdEmpleado')
                return result
            else:
                logger.warning(f"Empleado con ID {empleado_id} no encontrado en empleados")
                return None
        except Exception as e:
            logger.exception(f"Error obteniendo empleado {empleado_id} desde empleados: {e}")
            return None

    def get_empleado_by_identidad(self, identidad: str):
        """Buscar empleado en `empleados` por su `numero_identidad`.

        Retorna dict normalizado similar a `get_empleado` o `None` si no existe.
        """
        if not identidad:
            return None
        try:
            conn_emp = get_db_empleados()
            cur = conn_emp.cursor()
            # Verificar si la columna `numero_identidad` existe en la tabla empleados
            try:
                cur.execute("SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'empleados' AND COLUMN_NAME = 'numero_identidad'")
                col_exists = bool(cur.fetchone())
            except Exception:
                col_exists = False

            if not col_exists:
                logger.info('La columna numero_identidad no existe en empleados; salto búsqueda por identidad')
                return None

            cur.execute("SELECT id_empleado, codigo_empleado, nombre_completo, numero_identidad, empresa, puesto FROM empleados WHERE numero_identidad = ?", (identidad,))
            row = cur.fetchone()
            if row:
                cols = [c[0] for c in cur.description]
                res = dict(zip(cols, row))
                if 'NombreCompleto' in res and 'nombre_completo' not in res:
                    res['nombre_completo'] = res.get('NombreCompleto')
                if 'IdEmpleado' in res and 'id_empleado' not in res:
                    res['id_empleado'] = res.get('IdEmpleado')
                if 'NumeroIdentidad' in res and 'numero_identidad' not in res:
                    res['numero_identidad'] = res.get('NumeroIdentidad')
                return res
        except Exception as e:
            logger.warning(f"Error buscando empleado por identidad en empleados: {e}")
        return None

    def get_empleado_by_codigo(self, codigo: str):
        """Buscar empleado en `empleados` por su `codigo_empleado`.

        Retorna dict normalizado similar a `get_empleado` o `None` si no existe.
        """
        if not codigo:
            return None
        try:
            conn_emp = get_db_empleados()
            cur = conn_emp.cursor()
            cur.execute("SELECT id_empleado, codigo_empleado, nombre_completo, numero_identidad, empresa, puesto FROM empleados WHERE codigo_empleado = ?", (codigo,))
            row = cur.fetchone()
            if row:
                cols = [c[0] for c in cur.description]
                res = dict(zip(cols, row))
                if 'NombreCompleto' in res and 'nombre_completo' not in res:
                    res['nombre_completo'] = res.get('NombreCompleto')
                if 'IdEmpleado' in res and 'id_empleado' not in res:
                    res['id_empleado'] = res.get('IdEmpleado')
                if 'NumeroIdentidad' in res and 'numero_identidad' not in res:
                    res['numero_identidad'] = res.get('NumeroIdentidad')
                return res
        except Exception:
            pass
        return None

    def _get_empleado_nombre(self, empleado_id):
        """Devuelve el nombre completo del empleado consultando la BD empleados.
        Retorna `None` si no se encuentra o en caso de error.
        """
        if not empleado_id:
            return None
        try:
            conn_emp = get_db_empleados()
            cur = conn_emp.cursor()
            cur.execute("SELECT nombre_completo FROM empleados WHERE id_empleado = ?", (int(empleado_id),))
            row = cur.fetchone()
            if row and row[0]:
                return str(row[0])
        except Exception:
                logger.exception('Error obteniendo nombre de empleado %s desde empleados', empleado_id)
        return None

    # NOTE: Peripheral CRUD removed from service. If restoring the feature,
    # re-add list_perifericos/get_periferico/create_periferico/update_periferico/
    # delete_periferico here and corresponding DB table access.

    # CRUD para Planes
    def list_planes(self):
        cur = self.conn.cursor()
        cur.execute("""
                 SELECT p.id_plan, p.numero_linea, p.fecha_inicio, p.fecha_fin, p.costo_plan, p.moneda_plan,
                     COUNT(d.id_dispositivo) AS linked_count,
                     ld.categoria AS linked_tipo,
                     ld.nombre_marca AS linked_marca,
                     ld.nombre_modelo AS linked_modelo,
                     ld.numero_serie AS linked_numero_serie,
                     ld.imei AS linked_imei
            FROM planes p
            LEFT JOIN dispositivo d ON d.fk_id_plan = p.id_plan AND d.estado != 3
            OUTER APPLY (
                SELECT TOP 1 m.categoria, ma.nombre_marca, m.nombre_modelo, dd.numero_serie, dd.imei
                FROM dispositivo dd
                JOIN modelo m ON m.id_modelo = dd.fk_id_modelo
                LEFT JOIN marca ma ON ma.id_marca = m.fk_id_marca
                WHERE dd.fk_id_plan = p.id_plan AND dd.estado != 3
                ORDER BY dd.id_dispositivo ASC
            ) ld
            GROUP BY p.id_plan, p.numero_linea, p.fecha_inicio, p.fecha_fin, p.costo_plan, p.moneda_plan, ld.categoria, ld.nombre_marca, ld.nombre_modelo, ld.numero_serie, ld.imei
            ORDER BY p.id_plan DESC
        """)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def list_historico_planes(self):
        """Lista los registros de `historico_planes` para la vista histórica."""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT id_historico, id_plan, numero_linea, fecha_operacion, fecha_inicio, fecha_fin, costo_plan, moneda_plan
            FROM historico_planes
            ORDER BY fecha_operacion DESC
        """)
        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        # Normalizar fechas a ISO (YYYY-MM-DD) si es necesario
        for r in rows:
            try:
                if r.get('fecha_operacion') and hasattr(r.get('fecha_operacion'), 'isoformat'):
                    r['fecha_operacion'] = r['fecha_operacion'].isoformat()[:10]
            except Exception:
                pass
            try:
                if r.get('fecha_inicio') and hasattr(r.get('fecha_inicio'), 'isoformat'):
                    r['fecha_inicio'] = r['fecha_inicio'].isoformat()[:10]
            except Exception:
                pass
            try:
                if r.get('fecha_fin') and hasattr(r.get('fecha_fin'), 'isoformat'):
                    r['fecha_fin'] = r['fecha_fin'].isoformat()[:10]
            except Exception:
                pass
        return rows

    def get_devices_by_historico(self, historico_id: int):
        """Devuelve dispositivos vinculados a un registro de `historico_planes` (fk_id_historico_planes).

        Retorna lista de dicts con campos principales para mostrar en modal.
        """
        cur = self.conn.cursor()
        cur.execute("""
            SELECT d.id_dispositivo, d.numero_serie, d.identificador, d.imei, d.imei2, d.direccion_mac,
                   m.nombre_modelo, ma.nombre_marca, m.categoria as categoria, d.tamano, d.color, d.observaciones
            FROM dispositivo d
            LEFT JOIN modelo m ON d.fk_id_modelo = m.id_modelo
            LEFT JOIN marca ma ON m.fk_id_marca = ma.id_marca
            WHERE d.fk_id_historico_planes = ?
        """, (historico_id,))
        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        return rows

    def get_plane(self, plan_id: int):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT id_plan, numero_linea, fecha_inicio, fecha_fin, costo_plan, moneda_plan
            FROM planes
            WHERE id_plan = ?
        """, (plan_id,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [c[0] for c in cur.description]
        return dict(zip(cols, row))

    def create_plane(self, numero_linea: str, fecha_inicio: str, fecha_fin: str | None, costo_plan, moneda_plan: str = 'USD'):
        if not numero_linea or not fecha_inicio or costo_plan is None:
            raise ValueError('numero_linea, fecha_inicio y costo_plan son obligatorios')
        cur = self.conn.cursor()
        cur.execute(
            """INSERT INTO planes (numero_linea, fecha_inicio, fecha_fin, costo_plan, moneda_plan) 
            OUTPUT INSERTED.id_plan
            VALUES (?, ?, ?, ?, ?)""",
            (numero_linea, fecha_inicio, fecha_fin, costo_plan, moneda_plan)
        )
        result = cur.fetchone()
        if not result or result[0] is None:
            raise Exception("No se pudo obtener el ID del plan creado")
        new_id = int(result[0])
        self.conn.commit()
        return new_id

    def create_plane_pending(self, numero_linea: str, fecha_inicio: str, fecha_fin: str | None, costo_plan, moneda_plan: str = 'USD'):
        """Crear plan sin commit inmediato - para transacciones que requieren vinculación obligatoria.
        Retorna el ID del plan creado. El commit debe hacerse manualmente con confirm_plan_pending()."""
        if not numero_linea or not fecha_inicio or costo_plan is None:
            raise ValueError('numero_linea, fecha_inicio y costo_plan son obligatorios')
        cur = self.conn.cursor()
        cur.execute(
            """INSERT INTO planes (numero_linea, fecha_inicio, fecha_fin, costo_plan, moneda_plan) 
            OUTPUT INSERTED.id_plan
            VALUES (?, ?, ?, ?, ?)""",
            (numero_linea, fecha_inicio, fecha_fin, costo_plan, moneda_plan)
        )
        result = cur.fetchone()
        if not result or result[0] is None:
            raise Exception("No se pudo obtener el ID del plan creado")
        new_id = int(result[0])
        # NO commit aquí - la transacción queda abierta
        return new_id

    def confirm_plan_pending(self):
        """Confirma la transacción pendiente de un plan creado con create_plane_pending()"""
        self.conn.commit()

    def rollback_plan_pending(self):
        """Revierte los cambios si no se completó la vinculación del plan"""
        self.conn.rollback()

    def get_plane_by_numero_linea(self, numero_linea: str):
        """Busca un plan por número de línea (case-insensitive)"""
        if not numero_linea:
            return None
        cur = self.conn.cursor()
        cur.execute(
            "SELECT id_plan, numero_linea, fecha_inicio, fecha_fin, costo_plan, moneda_plan FROM planes WHERE LOWER(numero_linea) = LOWER(?)",
            (numero_linea,)
        )
        row = cur.fetchone()
        if row:
            return {
                'id_plan': row[0],
                'numero_linea': row[1],
                'fecha_inicio': row[2],
                'fecha_fin': row[3],
                'costo_plan': row[4],
                'moneda_plan': row[5]
            }
        return None

    def update_plane(self, plan_id: int, numero_linea: str, fecha_inicio: str, fecha_fin: str | None, costo_plan, moneda_plan: str = 'USD'):
        if not numero_linea or not fecha_inicio or costo_plan is None:
            raise ValueError('numero_linea, fecha_inicio y costo_plan son obligatorios')
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE planes SET numero_linea = ?, fecha_inicio = ?, fecha_fin = ?, costo_plan = ?, moneda_plan = ? WHERE id_plan = ?",
            (numero_linea, fecha_inicio, fecha_fin, costo_plan, moneda_plan, plan_id)
        )
        self.conn.commit()

    def delete_plane(self, plan_id: int):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM planes WHERE id_plan = ?", (plan_id,))
        self.conn.commit()

    def renew_plane(self, plan_id: int, fecha_inicio: str, fecha_fin: str | None, costo_plan, moneda_plan: str = 'L', device_id: int | None = None):
        """Renew a plan:
        1) Backup current plan into historico_planes
        2) Delete current plan from planes
        3) Create new plan with provided values (keeping numero_linea)
        4) If device_id provided, link it to the new plan
        Returns dict with ids created/updated.
        """
        cur = self.conn.cursor()
        try:
            # Start transaction
            self.conn.autocommit = False

            # Fetch existing plan
            cur.execute("SELECT id_plan, numero_linea, fecha_inicio, fecha_fin, costo_plan, moneda_plan FROM planes WHERE id_plan = ?", (plan_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError('Plan no encontrado')
            cols = [c[0] for c in cur.description]
            old = dict(zip(cols, row))

            # Insert into historico_planes
            cur.execute(
                """INSERT INTO historico_planes (id_plan, numero_linea, fecha_inicio, fecha_fin, costo_plan, moneda_plan) 
                OUTPUT INSERTED.id_historico
                VALUES (?, ?, ?, ?, ?, ?)""",
                (old.get('id_plan'), old.get('numero_linea'), old.get('fecha_inicio'), old.get('fecha_fin'), old.get('costo_plan'), old.get('moneda_plan'))
            )
            result = cur.fetchone()
            if not result:
                raise Exception("No se pudo obtener el ID del historial de planes")
            historico_id = int(result[0])
            logger.info('historico_planes created id=%s for old_plan_id=%s', historico_id, old.get('id_plan'))

            # Find devices linked to the old plan

            cur.execute("SELECT id_dispositivo FROM dispositivo WHERE fk_id_plan = ?", (plan_id,))
            dev_rows = cur.fetchall()
            dev_ids = [r[0] for r in dev_rows] if dev_rows else []
            
            # Track devices we've processed to avoid double-handling later
            processed_device_ids = set()
            if len(dev_ids) == 1:
                # Only update the single device: finalize assignment, then mark estado and historico
                d = dev_ids[0]
                try:
                    self.finalize_assignment_by_device(int(d), fecha_fin=None, commit=False)
                except Exception:
                    logger.exception('Could not finalize assignment for device %s during renew', d)
                # Update device estado to 3 and set historico link and observation
                motivo_baja = "Motivo baja: El teléfono procedió a renovación"
                cur.execute(
                    "UPDATE dispositivo SET estado = ?, fk_id_plan = NULL, fk_id_historico_planes = ?, observaciones = CONCAT(ISNULL(observaciones, ''), ' | ', ?) WHERE id_dispositivo = ?",
                    (3, historico_id, motivo_baja, int(d))
                )
                logger.info('Dispositivo %s marcado como estado=3 durante renovación. Rows affected: %s', int(d), cur.rowcount)
                processed_device_ids.add(d)
            elif len(dev_ids) > 1:
                # Unexpected: multiple devices linked to one plan. Log and update all to preserve referential integrity.
                logger.warning('Multiple devices (%s) linked to plan %s during renew; processing all.', dev_ids, plan_id)
                for drow in dev_ids:
                    try:
                        self.finalize_assignment_by_device(int(drow), fecha_fin=None, commit=False)
                    except Exception:
                        logger.exception('Could not finalize assignment for device %s during renew', drow)
                    motivo_baja = "Motivo baja: El teléfono procedió a renovación"
                    cur.execute(
                        "UPDATE dispositivo SET estado = ?, fk_id_plan = NULL, fk_id_historico_planes = ?, observaciones = CONCAT(ISNULL(observaciones, ''), ' | ', ?) WHERE id_dispositivo = ?",
                        (3, historico_id, motivo_baja, int(drow))
                    )
                    logger.info('Dispositivo %s marcado como estado=3 durante renovación (múltiple). Rows affected: %s', drow, cur.rowcount)
                    processed_device_ids.add(drow)
            else:
                # No devices linked; nothing to do
                processed_device_ids = set()

            # Delete the old plan
            cur.execute("DELETE FROM planes WHERE id_plan = ?", (plan_id,))

            # Create the new plan preserving numero_linea
            new_numero = old.get('numero_linea')
            cur.execute("""INSERT INTO planes (numero_linea, fecha_inicio, fecha_fin, costo_plan, moneda_plan)
                        OUTPUT INSERTED.id_plan
                        VALUES (?, ?, ?, ?, ?)""",
                        (new_numero, fecha_inicio, fecha_fin, costo_plan, moneda_plan))
            result = cur.fetchone()
            if not result:
                raise Exception("No se pudo obtener el ID del nuevo plan")
            new_plan_id = int(result[0])
            logger.info('New plan created id=%s', new_plan_id)

            # If a device was provided (explicit), LINK IT TO THE NEW PLAN
            device_updated = False
            if device_id:
                try:
                    did = int(device_id)
                except Exception:
                    did = None
                    
                if did:
                    # Check if this device was already processed (was linked to old plan)
                    if did in processed_device_ids:
                        # Device already went through finalize_assignment and estado=3
                        # Now just link it to the new plan and set estado back to 0 (Disponible) or 1 if has active assignment
                        # Check if device has an active assignment to determine correct estado
                        cur.execute(
                            "SELECT COUNT(*) FROM asignacion WHERE fk_id_dispositivo = ? AND (fecha_fin_asignacion IS NULL OR fecha_fin_asignacion = '')",
                            (did,)
                        )
                        has_active = cur.fetchone()[0] > 0
                        new_estado = 1 if has_active else 0
                        cur.execute(
                            "UPDATE dispositivo SET fk_id_plan = ?, estado = ? WHERE id_dispositivo = ?",
                            (new_plan_id, new_estado, did)
                        )
                        device_updated = (cur.rowcount > 0)
                        logger.info('Dispositivo %s vinculado al nuevo plan %s con estado=%s (reutilizado). Rows affected: %s', did, new_plan_id, new_estado, cur.rowcount)
                    else:
                        # This is a NEW device not previously linked to the old plan
                        try:
                            # Finalize any active assignment on this device
                            self.finalize_assignment_by_device(did, fecha_fin=None, commit=False)
                        except Exception:
                            logger.exception('Could not finalize assignment for device %s', did)
                        
                        # Check if device has an active assignment to determine correct estado
                        cur.execute(
                            "SELECT COUNT(*) FROM asignacion WHERE fk_id_dispositivo = ? AND (fecha_fin_asignacion IS NULL OR fecha_fin_asignacion = '')",
                            (did,)
                        )
                        has_active = cur.fetchone()[0] > 0
                        new_estado = 1 if has_active else 0
                        # Link the device to the new plan
                        cur.execute(
                            "UPDATE dispositivo SET fk_id_plan = ?, estado = ? WHERE id_dispositivo = ?",
                            (new_plan_id, new_estado, did)
                        )
                        device_updated = (cur.rowcount > 0)
                        logger.info('Dispositivo %s vinculado al nuevo plan %s con estado=%s (nuevo). Rows affected: %s', did, new_plan_id, new_estado, cur.rowcount)

            self.conn.commit()
            logger.info('Plan renewed: historico_id=%s, new_plan_id=%s', historico_id, new_plan_id)
            return {'historico_id': historico_id, 'new_plan_id': new_plan_id, 'device_updated': device_updated}
        except Exception:
            try:
                self.conn.rollback()
            except:
                pass
            raise
        finally:
            try:
                self.conn.autocommit = True
            except:
                pass

    def get_next_available_ip(self):
        """Obtiene la siguiente dirección IP disponible basada en la última registrada.
        Si la última es 192.168.0.26, devuelve 192.168.0.27.
        Si la última es 192.168.0.255, devuelve 192.168.1.0.
        Si no hay ninguna, devuelve 192.168.0.1.
        """
        cur = self.conn.cursor()
        try:
            # Obtener todas las IPs asignadas (excluyendo NULLs y vacíos)
            cur.execute(
                "SELECT ip_asignada FROM dispositivo WHERE ip_asignada IS NOT NULL AND ip_asignada != ''"
            )
            rows = cur.fetchall() or []

            # Construir conjunto de IPs ocupadas como enteros para búsqueda rápida
            import ipaddress
            occupied = set()
            for r in rows:
                try:
                    ipstr = str(r[0]).strip()
                    ipobj = ipaddress.IPv4Address(ipstr)
                    occupied.add(int(ipobj))
                except Exception:
                    # Ignorar entradas inválidas
                    continue

            # Rango de búsqueda: desde 192.168.0.2 hasta 192.168.255.254
            # (queremos empezar en .2 por requisitos de la red)
            start = ipaddress.IPv4Address('192.168.0.2')
            end = ipaddress.IPv4Address('192.168.255.254')

            # Buscar la primera IP libre en orden ascendente
            cur_ip = int(start)
            while cur_ip <= int(end):
                if cur_ip not in occupied:
                    return str(ipaddress.IPv4Address(cur_ip))
                cur_ip += 1

            # Si no quedan IPs en el rango, intentar regresar un fallback (suma al máximo existente)
            if occupied:
                max_ip = max(occupied)
                try:
                    cand = ipaddress.IPv4Address(max_ip + 1)
                    return str(cand)
                except Exception:
                    return '192.168.0.2'
            else:
                return '192.168.0.2'
        except Exception as e:
            logger.exception('Error getting next available IP')
            return '192.168.0.2'

    def find_device_by_ip(self, ip_address: str):
        """Devuelve el dispositivo que tiene asignada la IP (si existe).

        Retorna un diccionario con campos mínimos: id_dispositivo, categoria,
        nombre_marca, nombre_modelo. Si no existe, devuelve None.
        """
        try:
            if not ip_address:
                return None
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT d.id_dispositivo, m.categoria, ma.nombre_marca, m.nombre_modelo
                FROM dispositivo d
                JOIN modelo m ON m.id_modelo = d.fk_id_modelo
                LEFT JOIN marca ma ON ma.id_marca = m.fk_id_marca
                WHERE d.ip_asignada = ? AND d.ip_asignada IS NOT NULL AND d.ip_asignada != ''
                  AND ISNULL(d.estado, 0) != 3
                """,
                (ip_address,)
            )
            row = cur.fetchone()
            if not row:
                return None
            cols = [c[0] for c in cur.description]
            return dict(zip(cols, row))
        except Exception:
            logger.exception('Error buscando dispositivo por IP')
            return None

    def clear_ip(self, device_id: int):
        """Quita la IP asignada a un dispositivo (set ip_asignada = NULL).

        Devuelve True si se actualizó al menos una fila.
        """
        try:
            cur = self.conn.cursor()
            cur.execute("UPDATE dispositivo SET ip_asignada = NULL WHERE id_dispositivo = ?", (int(device_id),))
            self.conn.commit()
            return (cur.rowcount > 0)
        except Exception:
            try:
                self.conn.rollback()
            except:
                pass
            logger.exception('Error limpiando IP del dispositivo')
            return False

    def list_auditoria_logs(self, limit: int = 500):
        """Lista los registros de auditoría (últimas acciones registradas)"""
        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT id_auditoria, usuario, accion, tabla_afectada, id_registro, descripcion, fecha_accion
                FROM auditoria
                ORDER BY fecha_accion DESC
                OFFSET 0 ROWS FETCH NEXT ? ROWS ONLY
            """, (limit,))
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
        except Exception:
            logger.exception('Error listando logs de auditoría')
            return []

    # =====================================================
    # FASE 3 - MÉTODOS DE DOCUMENTACIÓN
    # =====================================================

    def update_asignacion_estado_doc(self, asignacion_id: int, estado: int):
        """
        Actualiza el estado de documentación de una asignación.
        
        Estados numéricos según doc/proceso.txt:
        - 0: Sin iniciar
        - 11-14: Flujo firma digital
        - 21-24: Flujo firma manual
        - 90: Completado
        - 99: Cancelado
        - X10, X20, X30, etc.: Estados de error
        
        Args:
            asignacion_id: ID de la asignación
            estado: Estado numérico de documentación
        
        Returns:
            bool: True si se actualizó correctamente
        """
        try:
            cur = self.conn.cursor()
            
            # Actualizar estado
            cur.execute("""
                UPDATE asignacion
                SET estado_documentacion = ?
                WHERE id_asignacion = ?
            """, (estado, asignacion_id))
            
            self.conn.commit()
            logger.info(f"Asignación {asignacion_id}: Estado de documentación actualizado a {estado}")
            return True
            
        except Exception as e:
            logger.error(f"Error actualizando estado de documentación: {str(e)}")
            return False

    def get_asignaciones_pendientes_documentacion(self):
        """
        Obtiene asignaciones pendientes de documentación.
        
        Returns:
            list: Lista de asignaciones con estado != 'completada'
        """
        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT 
                    a.id_asignacion,
                    a.fk_id_dispositivo,
                    a.fk_id_empleado,
                    a.estado_documentacion,
                    d.numero_serie,
                    d.identificador,
                    e.nombre_completo as empleado_nombre,
                    e.codigo_empleado
                FROM asignacion a
                LEFT JOIN dispositivo d ON d.id_dispositivo = a.fk_id_dispositivo
                LEFT JOIN empleados e ON e.id_empleado = a.fk_id_empleado
                WHERE a.estado_documentacion != 'completada'
                ORDER BY a.fecha_creacion DESC
            """)
            
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
            
        except Exception as e:
            logger.error(f"Error obteniendo asignaciones pendientes: {str(e)}")
            return []
