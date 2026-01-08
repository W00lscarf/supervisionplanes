# app.py  (COPIAR / PEGAR COMPLETO)
import os
import re
import json
import sqlite3
from datetime import date, datetime
from typing import Dict, Optional, List

import pandas as pd
import streamlit as st

# =========================================================
# CONFIG
# =========================================================
APP_TITLE = "Piloto PAS: Planificación y Confirmación de Supervisión"
DB_PATH = "rrd_supervision.db"                 # SQLite local (se crea solo)
UPLOAD_DIR = "uploads"
DIVISIONES_PATH = "divisiones_chile_utf8sig.csv"  # tu CSV en el repo

PERIODOS = [
    "Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre",
    "1° Trimestre","2° Trimestre","3° Trimestre","4° Trimestre","1° Semestre","2° Semestre","Anual"
]
TIPO_ACCION = ["Supervisión", "Seguimiento", "Verificación", "Actualización", "Simulacro", "Difusión", "Otro"]
TIPO_EVIDENCIA = ["Acta", "Informe", "Resolución/Decreto", "Registro fotográfico", "Lista asistencia", "Otro"]
ESTADO_EJECUCION = ["Sí", "No", "Parcial"]
TIPO_MOTIVO = ["Operativo", "Presupuestario", "Normativo", "Fuerza mayor", "Otro"]

DEPENDENCIAS = [
    "Direcciones Regionales",
    "Subdirección de Reducción del Riesgo de Desastres",
    "Subdirección de Gestión de Emergencias",
    "Subdirección de Desarrollo Estratégico",
]

# Placeholder: reemplaza por tu lista institucional si quieres
MINISTERIOS = [
    "(Seleccionar)",
    "Ministerio del Interior y Seguridad Pública",
    "Ministerio de Salud",
    "Ministerio de Obras Públicas",
    "Ministerio de Educación",
    "Ministerio de Vivienda y Urbanismo",
    "Ministerio de Transportes y Telecomunicaciones",
    "Ministerio de Energía",
    "Ministerio del Medio Ambiente",
    "Otro (especificar)",
]

# =========================================================
# CATÁLOGO DE INSTRUMENTOS (DINÁMICO POR DEPENDENCIA)
# - ambito: Nacional | Regional | Provincial | Comunal | Sectorial
# - requiere_entidad/tipo_entidad: para instrumentos "sectoriales" (ministerios u otros)
# Estructura por fila (8 campos):
# (id_instrumento, tipo_instrumento, nombre_instrumento, ambito, requiere_entidad, tipo_entidad, marco_normativo, dependencia_owner)
# =========================================================
INSTRUMENTOS = [
    # Direcciones Regionales
    ("DR-PLAN-RRD-COM", "Plan", "Planes para la RRD (Comunal)", "Comunal", 0, None, "Procedimiento PAS", "Direcciones Regionales"),
    ("DR-PLAN-EME-COM", "Plan", "Planes de Emergencia (Comunal)", "Comunal", 0, None, "Procedimiento PAS", "Direcciones Regionales"),
    ("DR-COGRID-REG", "Compromisos COGRID", "Compromisos COGRID Regional", "Regional", 0, None, "Procedimiento PAS", "Direcciones Regionales"),
    ("DR-COGRID-PRO", "Compromisos COGRID", "Compromisos COGRID Provincial", "Provincial", 0, None, "Procedimiento PAS", "Direcciones Regionales"),

    # Subdirección RRD
    ("SRRD-PEN-RRD", "Plan", "Plan Estratégico Nacional para la RRD", "Nacional", 0, None, "Procedimiento PAS", "Subdirección de Reducción del Riesgo de Desastres"),
    ("SRRD-PNE", "Plan", "Plan Nacional de Emergencia (y anexos)", "Nacional", 0, None, "Procedimiento PAS", "Subdirección de Reducción del Riesgo de Desastres"),

    # Sectorial (ministerios)
    ("SRRD-PLAN-SEC", "Plan", "Planes Sectoriales (Ministerios PN-RRD)", "Sectorial", 1, "Ministerio", "Procedimiento PAS", "Subdirección de Reducción del Riesgo de Desastres"),
    ("SRRD-MAP-AMEN", "Mapa", "Mapas de Amenaza (Ministerios PN-RRD)", "Sectorial", 1, "Ministerio", "Procedimiento PAS", "Subdirección de Reducción del Riesgo de Desastres"),

    # Territorial
    ("SRRD-EME-REG", "Plan", "Planes de Emergencia (Regional)", "Regional", 0, None, "Procedimiento PAS", "Subdirección de Reducción del Riesgo de Desastres"),
    ("SRRD-EME-PRO", "Plan", "Planes de Emergencia (Provincial)", "Provincial", 0, None, "Procedimiento PAS", "Subdirección de Reducción del Riesgo de Desastres"),
    ("SRRD-RRD-REG", "Plan", "Planes para la RRD (Regional)", "Regional", 0, None, "Procedimiento PAS", "Subdirección de Reducción del Riesgo de Desastres"),
    ("SRRD-MAP-RIES", "Mapa", "Mapas de Riesgo", "Regional", 0, None, "Procedimiento PAS", "Subdirección de Reducción del Riesgo de Desastres"),
    ("SRRD-COGRID-NAC-MP", "Compromisos COGRID", "COGRID Nacional (Mitigación/Preparación)", "Nacional", 0, None, "Procedimiento PAS", "Subdirección de Reducción del Riesgo de Desastres"),

    # Subdirección Gestión de Emergencias
    ("SGE-SAT", "SAT", "Sistema de Alerta Temprana (protocolos/simulaciones/monitoreo)", "Nacional", 0, None, "Procedimiento PAS", "Subdirección de Gestión de Emergencias"),
    ("SGE-COGRID-NAC-R", "Compromisos COGRID", "COGRID Nacional (Respuesta)", "Nacional", 0, None, "Procedimiento PAS", "Subdirección de Gestión de Emergencias"),

    # Subdirección Desarrollo Estratégico
    ("SDE-SINFO", "Sistema", "Sistema de Información", "Nacional", 0, None, "Procedimiento PAS", "Subdirección de Desarrollo Estratégico"),
]

# =========================================================
# UTILIDADES
# =========================================================
def ensure_dirs():
    os.makedirs(UPLOAD_DIR, exist_ok=True)

def make_id(prefix: str) -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    rnd = str(abs(hash((prefix, ts))) % 10000).zfill(4)
    return f"{prefix}-{ts}-{rnd}"

def save_uploaded_file(file) -> Optional[str]:
    if file is None:
        return None
    safe_name = re.sub(r"[\\/]+", "_", file.name.replace("..", ""))
    stamped = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_name = f"{stamped}__{safe_name}"
    out_path = os.path.join(UPLOAD_DIR, out_name)
    with open(out_path, "wb") as f:
        f.write(file.getbuffer())
    return out_path

# =========================================================
# DIVISIONES (REGION/PROVINCIA/COMUNA)
# =========================================================
@st.cache_data
def load_divisiones(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
    df.columns = [c.lower().strip() for c in df.columns]
    for c in ["region", "provincia", "comuna"]:
        df[c] = df[c].astype(str).str.replace("\u00a0", " ", regex=False).str.strip()
    df = df.dropna(subset=["region","provincia","comuna"]).drop_duplicates()
    return df

def regiones(df: pd.DataFrame) -> List[str]:
    return sorted(df["region"].dropna().unique().tolist())

def provincias(df: pd.DataFrame, region: str) -> List[str]:
    return sorted(df.loc[df["region"] == region, "provincia"].dropna().unique().tolist())

def comunas(df: pd.DataFrame, region: str, provincia: str) -> List[str]:
    mask = (df["region"] == region) & (df["provincia"] == provincia)
    return sorted(df.loc[mask, "comuna"].dropna().unique().tolist())

def territorial_requirements(ambito: str) -> Dict[str, bool]:
    a = (ambito or "").strip().lower()
    if a == "nacional":
        return {"region": False, "provincia": False, "comuna": False}
    if a == "regional":
        return {"region": True, "provincia": False, "comuna": False}
    if a == "provincial":
        return {"region": True, "provincia": True, "comuna": False}
    if a == "comunal":
        return {"region": True, "provincia": True, "comuna": True}
    if a == "sectorial":
        return {"region": False, "provincia": False, "comuna": False}
    return {"region": False, "provincia": False, "comuna": False}

def territory_selector(df_div: pd.DataFrame, req: Dict[str, bool], prefix: str = "") -> Dict[str, Optional[str]]:
    """
    Cascada real con disabled y reseteo.
    Retorna None donde no aplica.
    """
    k_region = f"{prefix}region_sel"
    k_prov = f"{prefix}provincia_sel"
    k_com = f"{prefix}comuna_sel"
    k_region_prev = f"{prefix}region_prev"
    k_prov_prev = f"{prefix}provincia_prev"

    for k, default in [(k_region,"(No aplica)"), (k_prov,"(No aplica)"), (k_com,"(No aplica)"), (k_region_prev,None), (k_prov_prev,None)]:
        if k not in st.session_state:
            st.session_state[k] = default

    if not req["region"]:
        return {"region": None, "provincia": None, "comuna": None}

    region = st.selectbox("Región", ["(No aplica)"] + regiones(df_div), key=k_region)

    if region != st.session_state[k_region_prev]:
        st.session_state[k_prov] = "(No aplica)"
        st.session_state[k_com] = "(No aplica)"
        st.session_state[k_region_prev] = region

    if not req["provincia"]:
        return {"region": None if region=="(No aplica)" else region, "provincia": None, "comuna": None}

    prov_disabled = (region == "(No aplica)")
    prov_options = ["(No aplica)"] + (provincias(df_div, region) if not prov_disabled else [])
    provincia = st.selectbox("Provincia", prov_options, key=k_prov, disabled=prov_disabled)

    if provincia != st.session_state[k_prov_prev]:
        st.session_state[k_com] = "(No aplica)"
        st.session_state[k_prov_prev] = provincia

    if not req["comuna"]:
        return {
            "region": None if region=="(No aplica)" else region,
            "provincia": None if provincia=="(No aplica)" else provincia,
            "comuna": None
        }

    com_disabled = (region == "(No aplica)") or (provincia == "(No aplica)")
    com_options = ["(No aplica)"] + (comunas(df_div, region, provincia) if not com_disabled else [])
    comuna = st.selectbox("Comuna", com_options, key=k_com, disabled=com_disabled)

    return {
        "region": None if region=="(No aplica)" else region,
        "provincia": None if provincia=="(No aplica)" else provincia,
        "comuna": None if comuna=="(No aplica)" else comuna
    }

# =========================================================
# SQL (SQLite) - MIGRACIÓN AUTOMÁTICA
# =========================================================
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def _table_cols(cur, table_name: str):
    cur.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cur.fetchall()}

def _ensure_columns(cur, table: str, expected: dict):
    existing = _table_cols(cur, table)
    for col, coltype in expected.items():
        if col not in existing:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # Tablas base
    cur.execute("""
    CREATE TABLE IF NOT EXISTS instrumentos (
        id_instrumento TEXT PRIMARY KEY,
        tipo_instrumento TEXT,
        nombre_instrumento TEXT,
        ambito TEXT,
        requiere_entidad INTEGER,
        tipo_entidad TEXT,
        marco_normativo TEXT,
        dependencia_owner TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS planificaciones (
        id_planificacion TEXT PRIMARY KEY,
        dependencia TEXT,
        id_instrumento TEXT NOT NULL,
        tipo_instrumento TEXT,
        nombre_instrumento TEXT,
        ambito TEXT,
        region TEXT,
        provincia TEXT,
        comuna TEXT,
        entidad_objetivo TEXT,
        anio INTEGER,
        periodo_planificado TEXT,
        tipo_accion TEXT,
        responsable_planificacion TEXT,
        cargo_responsable_planificacion TEXT,
        email_responsable_planificacion TEXT,
        fecha_registro TEXT,
        observaciones TEXT,
        FOREIGN KEY(id_instrumento) REFERENCES instrumentos(id_instrumento)
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS reportes (
        id_reporte TEXT PRIMARY KEY,
        id_planificacion TEXT NOT NULL,
        ejecutado TEXT,
        fecha_ejecucion TEXT,
        tipo_evidencia TEXT,
        evidencia_path TEXT,
        responsable_reporte TEXT,
        cargo_responsable_reporte TEXT,
        email_responsable_reporte TEXT,
        fecha_reporte TEXT,
        observaciones TEXT,
        motivo_no_ejecucion TEXT,
        tipo_motivo TEXT,
        reprograma TEXT,
        FOREIGN KEY(id_planificacion) REFERENCES planificaciones(id_planificacion)
    )
    """)
    conn.commit()

    # Migración defensiva (si vienes de versión vieja)
    _ensure_columns(cur, "instrumentos", {
        "id_instrumento": "TEXT",
        "tipo_instrumento": "TEXT",
        "nombre_instrumento": "TEXT",
        "ambito": "TEXT",
        "requiere_entidad": "INTEGER",
        "tipo_entidad": "TEXT",
        "marco_normativo": "TEXT",
        "dependencia_owner": "TEXT",
    })
    _ensure_columns(cur, "planificaciones", {
        "ambito": "TEXT",
        "entidad_objetivo": "TEXT",
    })
    conn.commit()

    # Upsert catálogo de instrumentos (8 columnas)
    cur.executemany("""
    INSERT OR REPLACE INTO instrumentos
    (id_instrumento, tipo_instrumento, nombre_instrumento, ambito, requiere_entidad, tipo_entidad, marco_normativo, dependencia_owner)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, INSTRUMENTOS)
    conn.commit()
    conn.close()

def fetch_instrumentos() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM instrumentos ORDER BY dependencia_owner, tipo_instrumento, ambito, nombre_instrumento",
        conn
    )
    conn.close()
    return df

def insert_planificacion(payload: Dict):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO planificaciones (
        id_planificacion, dependencia, id_instrumento, tipo_instrumento, nombre_instrumento, ambito,
        region, provincia, comuna, entidad_objetivo, anio, periodo_planificado, tipo_accion,
        responsable_planificacion, cargo_responsable_planificacion, email_responsable_planificacion,
        fecha_registro, observaciones
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        payload["id_planificacion"], payload["dependencia"], payload["id_instrumento"],
        payload["tipo_instrumento"], payload["nombre_instrumento"], payload["ambito"],
        payload["region"], payload["provincia"], payload["comuna"], payload["entidad_objetivo"],
        payload["anio"], payload["periodo_planificado"], payload["tipo_accion"],
        payload["responsable_planificacion"], payload["cargo_responsable_planificacion"],
        payload["email_responsable_planificacion"], payload["fecha_registro"], payload["observaciones"]
    ))
    conn.commit()
    conn.close()

def insert_reporte(payload: Dict):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO reportes (
        id_reporte, id_planificacion, ejecutado, fecha_ejecucion, tipo_evidencia, evidencia_path,
        responsable_reporte, cargo_responsable_reporte, email_responsable_reporte, fecha_reporte, observaciones,
        motivo_no_ejecucion, tipo_motivo, reprograma
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        payload["id_reporte"], payload["id_planificacion"], payload["ejecutado"], payload["fecha_ejecucion"],
        payload["tipo_evidencia"], payload["evidencia_path"], payload["responsable_reporte"],
        payload["cargo_responsable_reporte"], payload["email_responsable_reporte"], payload["fecha_reporte"],
        payload["observaciones"], payload["motivo_no_ejecucion"], payload["tipo_motivo"], payload["reprograma"]
    ))
    conn.commit()
    conn.close()

def fetch_planificaciones() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM planificaciones ORDER BY fecha_registro DESC", conn)
    conn.close()
    return df

def fetch_reportes() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM reportes ORDER BY fecha_reporte DESC", conn)
    conn.close()
    return df

def fetch_planificacion_by_id(id_planificacion: str) -> Optional[pd.Series]:
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM planificaciones WHERE id_planificacion = ?", conn, params=[id_planificacion])
    conn.close()
    if df.empty:
        return None
    return df.iloc[0]

def has_reporte_for_planificacion(id_planificacion: str) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(1) FROM reportes WHERE id_planificacion = ?", (id_planificacion,))
    n = cur.fetchone()[0]
    conn.close()
    return n > 0

# =========================================================
# APP
# =========================================================
def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)

    if not os.path.exists(DIVISIONES_PATH):
        st.error(f"No se encontró {DIVISIONES_PATH}. Súbelo al repo (misma carpeta que app.py) o ajusta DIVISIONES_PATH.")
        st.stop()

    ensure_dirs()
    init_db()

    df_div = load_divisiones(DIVISIONES_PATH)
    inst_df = fetch_instrumentos()

    tab1, tab2, tab3 = st.tabs(["1) Planificación", "2) Confirmación / Reporte", "3) Registros"])

    # ---------------- TAB 1 ----------------
    with tab1:
        st.subheader("1) Planificación (cuándo se aplicará el instrumento)")

        with st.form("form_planificacion", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)

            with c1:
                dependencia = st.selectbox("Dependencia", DEPENDENCIAS)

                inst_dep = inst_df[inst_df["dependencia_owner"] == dependencia].copy()
                tipo_instrumento = st.selectbox("Tipo de instrumento", sorted(inst_dep["tipo_instrumento"].unique().tolist()))

                inst_dep2 = inst_dep[inst_dep["tipo_instrumento"] == tipo_instrumento].copy()
                instrumento_nombre = st.selectbox("Instrumento", inst_dep2["nombre_instrumento"].tolist())

                row = inst_dep2[inst_dep2["nombre_instrumento"] == instrumento_nombre].iloc[0]
                id_instrumento = row["id_instrumento"]
                ambito = row["ambito"]
                requiere_entidad = int(row["requiere_entidad"])
                tipo_entidad = row["tipo_entidad"]

                st.caption(f"Ámbito: {ambito} | ID: {id_instrumento}")

            with c2:
                anio = st.number_input("Año", min_value=2020, max_value=2100, value=date.today().year, step=1)
                periodo_planificado = st.selectbox("Periodo planificado", PERIODOS)
                tipo_accion = st.selectbox("Tipo aplicación", TIPO_ACCION)
                fecha_registro = st.date_input("Fecha registro", value=date.today())

                entidad_objetivo = None
                if requiere_entidad == 1:
                    if tipo_entidad == "Ministerio":
                        m = st.selectbox("Ministerio objetivo", MINISTERIOS)
                        if m == "Otro (especificar)":
                            entidad_objetivo = st.text_input("Especifica el ministerio/institución", value="").strip() or None
                        elif m == "(Seleccionar)":
                            entidad_objetivo = None
                        else:
                            entidad_objetivo = m
                    else:
                        entidad_objetivo = st.text_input("Entidad objetivo", value="").strip() or None

            with c3:
                req = territorial_requirements(ambito)
                territorio = territory_selector(df_div, req, prefix="plan_")

                responsable = st.text_input("Responsable planificación (nombre)", value="")
                cargo = st.text_input("Cargo (opcional)", value="")
                email = st.text_input("Email (opcional)", value="")

            observaciones = st.text_area("Observaciones", height=110)
            submitted = st.form_submit_button("Guardar planificación")

            if submitted:
                if not responsable.strip():
                    st.error("Debes indicar el responsable de planificación.")
                    st.stop()

                # Validaciones por ámbito
                if req["region"] and territorio["region"] is None:
                    st.error("Este instrumento exige Región.")
                    st.stop()
                if req["provincia"] and territorio["provincia"] is None:
                    st.error("Este instrumento exige Provincia.")
                    st.stop()
                if req["comuna"] and territorio["comuna"] is None:
                    st.error("Este instrumento exige Comuna.")
                    st.stop()

                if requiere_entidad == 1 and not entidad_objetivo:
                    st.error("Este instrumento exige seleccionar una entidad objetivo (p. ej., Ministerio).")
                    st.stop()

                payload = {
                    "id_planificacion": make_id("PLA"),
                    "dependencia": dependencia,
                    "id_instrumento": id_instrumento,
                    "tipo_instrumento": tipo_instrumento,
                    "nombre_instrumento": instrumento_nombre,
                    "ambito": ambito,
                    "region": territorio["region"],
                    "provincia": territorio["provincia"],
                    "comuna": territorio["comuna"],
                    "entidad_objetivo": entidad_objetivo,
                    "anio": int(anio),
                    "periodo_planificado": periodo_planificado,
                    "tipo_accion": tipo_accion,
                    "responsable_planificacion": responsable.strip(),
                    "cargo_responsable_planificacion": cargo.strip() or None,
                    "email_responsable_planificacion": email.strip() or None,
                    "fecha_registro": str(fecha_registro),
                    "observaciones": observaciones.strip() or None,
                }
                insert_planificacion(payload)
                st.success(f"Planificación guardada. ID: {payload['id_planificacion']}")

    # ---------------- TAB 2 ----------------
    with tab2:
        st.subheader("2) Confirmación / Reporte (se realizó lo planificado)")

        plan_df = fetch_planificaciones()
        if plan_df.empty:
            st.info("No hay planificaciones registradas.")
        else:
            plan_df["tiene_reporte"] = plan_df["id_planificacion"].apply(has_reporte_for_planificacion)
            show_all = st.checkbox("Mostrar también planificaciones ya confirmadas", value=False)
            view = plan_df if show_all else plan_df[~plan_df["tiene_reporte"]].copy()

            view["label"] = view.apply(
                lambda r: (
                    f'{r["id_planificacion"]} | {r["dependencia"]} | {r["tipo_instrumento"]}/{r["ambito"]} | '
                    f'{(r["region"] or "-")} / {(r["provincia"] or "-")} / {(r["comuna"] or "-")} | '
                    f'Entidad: {(r["entidad_objetivo"] or "-")} | {r["nombre_instrumento"]} | {r["anio"]} {r["periodo_planificado"]}'
                ),
                axis=1
            )

            sel = st.selectbox("Selecciona una planificación", view["label"].tolist())
            id_plan_sel = sel.split(" | ")[0].strip()
            plan_row = fetch_planificacion_by_id(id_plan_sel)

            # Mostrar SIEMPRE como JSON válido (no se arma string manual)
            resumen = {
                "ID Planificación": plan_row["id_planificacion"],
                "Dependencia": plan_row["dependencia"],
                "Instrumento": plan_row["nombre_instrumento"],
                "Tipo / Ámbito": f'{plan_row["tipo_instrumento"]} / {plan_row["ambito"]}',
                "Entidad objetivo": plan_row["entidad_objetivo"],
                "Territorio": {
                    "Región": plan_row["region"],
                    "Provincia": plan_row["provincia"],
                    "Comuna": plan_row["comuna"],
                },
                "Periodo": f'{plan_row["anio"]} - {plan_row["periodo_planificado"]}',
                "Tipo aplicación": plan_row["tipo_accion"],
                "Responsable planificación": plan_row["responsable_planificacion"],
            }

            st.write("**Resumen (formato correcto)**")
            st.json(resumen)
            st.code(json.dumps(resumen, ensure_ascii=False, indent=2), language="json")

            st.divider()

            with st.form("form_reporte", clear_on_submit=True):
                r1, r2, r3 = st.columns(3)
                with r1:
                    ejecutado = st.selectbox("¿Se ejecutó lo planificado?", ESTADO_EJECUCION)
                    fecha_ejecucion = st.date_input("Fecha de ejecución", value=date.today())
                    tipo_evidencia = st.selectbox("Tipo de evidencia", TIPO_EVIDENCIA)

                with r2:
                    evidencia_file = st.file_uploader("Adjuntar evidencia", type=["pdf","doc","docx","xls","xlsx","png","jpg","jpeg"])
                    responsable_rep = st.text_input("Responsable reporte (nombre)", value="")
                    cargo_rep = st.text_input("Cargo (opcional)", value="")

                with r3:
                    email_rep = st.text_input("Email (opcional)", value="")
                    fecha_reporte = st.date_input("Fecha de reporte", value=date.today())
                    obs_rep = st.text_area("Observaciones", height=110)

                motivo_no = ""
                tipo_motivo = ""
                reprograma = ""
                if ejecutado in ["No", "Parcial"]:
                    st.markdown("**Justificación (solo si No/Parcial):**")
                    j1, j2, j3 = st.columns([2,1,1])
                    with j1:
                        motivo_no = st.text_input("Motivo / explicación", value="")
                    with j2:
                        tipo_motivo = st.selectbox("Tipo de motivo", TIPO_MOTIVO)
                    with j3:
                        reprograma = st.selectbox("¿Se reprogramará?", ["Sí","No"])

                submit_rep = st.form_submit_button("Guardar confirmación")

                if submit_rep:
                    if not responsable_rep.strip():
                        st.error("Debes indicar el responsable del reporte.")
                        st.stop()

                    evidencia_path = save_uploaded_file(evidencia_file)
                    payload = {
                        "id_reporte": make_id("REP"),
                        "id_planificacion": id_plan_sel,
                        "ejecutado": ejecutado,
                        "fecha_ejecucion": str(fecha_ejecucion),
                        "tipo_evidencia": tipo_evidencia,
                        "evidencia_path": evidencia_path,
                        "responsable_reporte": responsable_rep.strip(),
                        "cargo_responsable_reporte": cargo_rep.strip() or None,
                        "email_responsable_reporte": email_rep.strip() or None,
                        "fecha_reporte": str(fecha_reporte),
                        "observaciones": obs_rep.strip() or None,
                        "motivo_no_ejecucion": motivo_no.strip() or None,
                        "tipo_motivo": tipo_motivo or None,
                        "reprograma": reprograma or None,
                    }
                    insert_reporte(payload)
                    st.success("Confirmación guardada.")

    # ---------------- TAB 3 ----------------
    with tab3:
        st.subheader("3) Registros (descarga para respaldo del piloto)")

        dfp = fetch_planificaciones()
        dfr = fetch_reportes()

        c1, c2 = st.columns(2)
        with c1:
            st.write("**Planificaciones**")
            st.dataframe(dfp, use_container_width=True, height=320)
            if not dfp.empty:
                st.download_button("Descargar planificaciones (CSV)", dfp.to_csv(index=False).encode("utf-8"),
                                   file_name="planificaciones.csv", mime="text/csv")
        with c2:
            st.write("**Confirmaciones/Reportes**")
            st.dataframe(dfr, use_container_width=True, height=320)
            if not dfr.empty:
                st.download_button("Descargar reportes (CSV)", dfr.to_csv(index=False).encode("utf-8"),
                                   file_name="reportes.csv", mime="text/csv")

        st.divider()
        if not dfp.empty:
            merged = dfp.merge(dfr, on="id_planificacion", how="left", suffixes=("_plan","_rep"))
            st.write("**Consolidado**")
            st.dataframe(merged, use_container_width=True, height=380)
            st.download_button("Descargar consolidado (CSV)", merged.to_csv(index=False).encode("utf-8"),
                               file_name="consolidado_piloto.csv", mime="text/csv")

        st.caption("Nota: SQLite se crea automáticamente al ejecutar. En Streamlit Cloud puede ser efímero; use exportación CSV para respaldo del piloto.")

if __name__ == "__main__":
    main()
