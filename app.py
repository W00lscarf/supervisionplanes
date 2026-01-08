# app.py
import os
import sqlite3
from datetime import date, datetime
from typing import Dict, Optional, List

import pandas as pd
import streamlit as st

APP_TITLE = "Plan Anual de Supervisión: Planificación y Reporte (RRD/SGE)"
DB_PATH = "rrd_supervision.db"
UPLOAD_DIR = "uploads"
DIVISIONES_PATH = "divisiones_chile.csv"  # Debe tener columnas: region, provincia, comuna

# ---------------------------------------------------------
# Dependencias / Responsables de Supervisión (del procedimiento)
# Fuente: Procedimiento del Plan Anual de Supervisión :contentReference[oaicite:2]{index=2}
# ---------------------------------------------------------
DEPENDENCIAS = [
    "Direcciones Regionales",
    "Subdirección de Reducción del Riesgo de Desastres",
    "Subdirección de Gestión de Emergencias",
    "Subdirección de Desarrollo Estratégico",
    # (Si luego incorporas otras unidades, agrégalas aquí)
]

# ---------------------------------------------------------
# Catálogo de instrumentos (ajustable) + asignación por dependencia
# Alineado al listado de instrumentos/ámbitos por dependencia del procedimiento :contentReference[oaicite:3]{index=3}
# ---------------------------------------------------------
INSTRUMENTOS = [
    # id, tipo, nombre, nivel_territorial, marco, dependencia_owner
    ("RRD-NAC-001", "RRD", "Plan Estratégico Nacional para la RRD", "Nacional",
     "Ley 21.364 / D.S. 86/2023 / Procedimiento PAS", "Subdirección de Reducción del Riesgo de Desastres"),
    ("EME-NAC-001", "Emergencia", "Plan Nacional de Emergencia (y anexos)", "Nacional",
     "Ley 21.364 / D.S. 86/2023 / Procedimiento PAS", "Subdirección de Reducción del Riesgo de Desastres"),

    ("RRD-REG-001", "RRD", "Plan Regional para la RRD", "Regional",
     "Ley 21.364 / D.S. 86/2023 / Procedimiento PAS", "Subdirección de Reducción del Riesgo de Desastres"),
    ("EME-REG-001", "Emergencia", "Plan Regional de Emergencia", "Regional",
     "Ley 21.364 / D.S. 86/2023 / Procedimiento PAS", "Subdirección de Reducción del Riesgo de Desastres"),
    ("EME-PRO-001", "Emergencia", "Plan Provincial de Emergencia", "Provincial",
     "Ley 21.364 / D.S. 86/2023 / Procedimiento PAS", "Subdirección de Reducción del Riesgo de Desastres"),

    ("RRD-COM-001", "RRD", "Plan Comunal para la RRD", "Comunal",
     "Ley 21.364 / D.S. 86/2023 / Procedimiento PAS", "Direcciones Regionales"),
    ("EME-COM-001", "Emergencia", "Plan Comunal de Emergencia", "Comunal",
     "Ley 21.364 / D.S. 86/2023 / Procedimiento PAS", "Direcciones Regionales"),

    ("MAP-AME-001", "Mapa", "Mapas de Amenaza", "Sectorial/Nacional",
     "Ley 21.364 / D.S. 86/2023 / Procedimiento PAS", "Subdirección de Reducción del Riesgo de Desastres"),
    ("MAP-RIE-001", "Mapa", "Mapas de Riesgo", "Nacional/Regional",
     "Ley 21.364 / D.S. 86/2023 / Procedimiento PAS", "Subdirección de Reducción del Riesgo de Desastres"),

    ("SAT-PRO-001", "SAT", "Sistema de Alerta Temprana (protocolos/simulaciones)", "Nacional/Regional",
     "Ley 21.364 / D.S. 86/2023 / Procedimiento PAS", "Subdirección de Gestión de Emergencias"),

    ("SINFO-001", "Sistema", "Sistema de Información", "Nacional",
     "Ley 21.364 / D.S. 86/2023 / Procedimiento PAS", "Subdirección de Desarrollo Estratégico"),

    ("COGRID-NAC-001", "Compromisos COGRID", "Compromisos COGRID Nacional (Mitigación/Preparación)", "Nacional",
     "Ley 21.364 / D.S. 234/2022 / Procedimiento PAS", "Subdirección de Reducción del Riesgo de Desastres"),
    ("COGRID-NAC-002", "Compromisos COGRID", "Compromisos COGRID Nacional (Respuesta)", "Nacional",
     "Ley 21.364 / D.S. 234/2022 / Procedimiento PAS", "Subdirección de Gestión de Emergencias"),
    ("COGRID-REG-001", "Compromisos COGRID", "Compromisos COGRID Regional", "Regional",
     "Ley 21.364 / D.S. 234/2022 / Procedimiento PAS", "Direcciones Regionales"),
    ("COGRID-PRO-001", "Compromisos COGRID", "Compromisos COGRID Provincial", "Provincial",
     "Ley 21.364 / D.S. 234/2022 / Procedimiento PAS", "Direcciones Regionales"),
]

PERIODOS = [
    "Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre",
    "1° Trimestre","2° Trimestre","3° Trimestre","4° Trimestre","1° Semestre","2° Semestre","Anual"
]
TIPO_APLICACION = ["Supervisión", "Seguimiento", "Verificación", "Actualización", "Simulacro", "Difusión", "Otro"]
TIPO_EVIDENCIA = ["Acta", "Informe", "Resolución/Decreto", "Registro fotográfico", "Lista asistencia", "Otro"]
ESTADO_EJECUCION = ["Sí", "No", "Parcial"]
TIPO_MOTIVO = ["Operativo", "Presupuestario", "Normativo", "Fuerza mayor", "Otro"]

# ---------------------------------------------------------
# Helpers: territorio dinámico
# ---------------------------------------------------------
@st.cache_data
def load_divisiones(path: str) -> pd.DataFrame:
    if os.path.exists(path):
        df = pd.read_csv(path, dtype=str)
        cols = [c.lower().strip() for c in df.columns]
        df.columns = cols
        required = {"region", "provincia", "comuna"}
        if not required.issubset(set(cols)):
            raise ValueError("divisiones_chile.csv debe tener columnas: region, provincia, comuna")
        # Normalizar espacios
        for c in ["region", "provincia", "comuna"]:
            df[c] = df[c].astype(str).str.strip()
        df = df.dropna(subset=["region", "provincia", "comuna"])
        return df
    # Fallback mínimo (solo para que no se rompa si falta CSV)
    return pd.DataFrame(
        [
            ("Biobío", "Concepción", "Concepción"),
            ("Biobío", "Concepción", "Talcahuano"),
            ("Biobío", "Arauco", "Arauco"),
            ("Biobío", "Biobío", "Los Ángeles"),
        ],
        columns=["region", "provincia", "comuna"]
    )

def regiones_from_df(df: pd.DataFrame) -> List[str]:
    return sorted(df["region"].dropna().unique().tolist())

def provincias_for_region(df: pd.DataFrame, region: str) -> List[str]:
    return sorted(df.loc[df["region"] == region, "provincia"].dropna().unique().tolist())

def comunas_for_provincia(df: pd.DataFrame, region: str, provincia: str) -> List[str]:
    dff = df[(df["region"] == region) & (df["provincia"] == provincia)]
    return sorted(dff["comuna"].dropna().unique().tolist())

# ---------------------------------------------------------
# DB
# ---------------------------------------------------------
def ensure_dirs():
    os.makedirs(UPLOAD_DIR, exist_ok=True)

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS instrumentos (
        id_instrumento TEXT PRIMARY KEY,
        tipo_instrumento TEXT,
        nombre_instrumento TEXT,
        nivel_territorial TEXT,
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
        nivel_territorial TEXT,
        region TEXT,
        provincia TEXT,
        comuna TEXT,
        anio INTEGER,
        periodo_planificado TEXT,
        tipo_aplicacion TEXT,
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

    cur.executemany("""
    INSERT OR REPLACE INTO instrumentos
    (id_instrumento, tipo_instrumento, nombre_instrumento, nivel_territorial, marco_normativo, dependencia_owner)
    VALUES (?, ?, ?, ?, ?, ?)
    """, INSTRUMENTOS)

    conn.commit()
    conn.close()

def fetch_instrumentos() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM instrumentos ORDER BY dependencia_owner, tipo_instrumento, nivel_territorial, nombre_instrumento",
        conn
    )
    conn.close()
    return df

def insert_planificacion(payload: Dict):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO planificaciones (
        id_planificacion, dependencia, id_instrumento, tipo_instrumento, nombre_instrumento, nivel_territorial,
        region, provincia, comuna, anio, periodo_planificado, tipo_aplicacion,
        responsable_planificacion, cargo_responsable_planificacion, email_responsable_planificacion,
        fecha_registro, observaciones
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        payload["id_planificacion"], payload["dependencia"], payload["id_instrumento"],
        payload["tipo_instrumento"], payload["nombre_instrumento"], payload["nivel_territorial"],
        payload["region"], payload["provincia"], payload["comuna"], payload["anio"], payload["periodo_planificado"],
        payload["tipo_aplicacion"], payload["responsable_planificacion"], payload["cargo_responsable_planificacion"],
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

def fetch_planificaciones(filters: Dict) -> pd.DataFrame:
    conn = get_conn()
    query = "SELECT * FROM planificaciones WHERE 1=1"
    params = []
    if filters.get("anio"):
        query += " AND anio = ?"
        params.append(filters["anio"])
    if filters.get("region") and filters["region"] != "Todas":
        query += " AND region = ?"
        params.append(filters["region"])
    if filters.get("dependencia") and filters["dependencia"] != "Todas":
        query += " AND dependencia = ?"
        params.append(filters["dependencia"])
    query += " ORDER BY fecha_registro DESC"
    df = pd.read_sql_query(query, conn, params=params)
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

def make_id(prefix: str) -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    rnd = str(abs(hash((prefix, ts))) % 10000).zfill(4)
    return f"{prefix}-{ts}-{rnd}"

def save_uploaded_file(file) -> str:
    if file is None:
        return ""
    safe_name = file.name.replace("..", "").replace("/", "_").replace("\\", "_")
    stamped = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_name = f"{stamped}__{safe_name}"
    out_path = os.path.join(UPLOAD_DIR, out_name)
    with open(out_path, "wb") as f:
        f.write(file.getbuffer())
    return out_path

# ---------------------------------------------------------
# Reglas de aplicabilidad territorial
# ---------------------------------------------------------
def territorial_fields_for_level(nivel: str) -> Dict[str, bool]:
    """
    Indica qué campos se deben solicitar (region/provincia/comuna) según nivel.
    """
    nivel = (nivel or "").strip().lower()
    if nivel == "nacional":
        return {"region": False, "provincia": False, "comuna": False}
    if nivel == "regional":
        return {"region": True, "provincia": False, "comuna": False}
    if nivel == "provincial":
        return {"region": True, "provincia": True, "comuna": False}
    if nivel == "comunal":
        return {"region": True, "provincia": True, "comuna": True}
    # Sectorial/Nacional, Nacional/Regional, etc.: por defecto, permitir región opcional
    return {"region": True, "provincia": False, "comuna": False}

# ---------------------------------------------------------
# UI
# ---------------------------------------------------------
def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)

    st.caption(
        "La lógica de instrumentos por dependencia y el alcance del Plan Anual de Supervisión se basa en el "
        "Procedimiento del Plan Anual de Supervisión. :contentReference[oaicite:4]{index=4}"
    )

    ensure_dirs()
    init_db()

    divisiones_df = load_divisiones(DIVISIONES_PATH)
    inst_df = fetch_instrumentos()

    tab1, tab2, tab3 = st.tabs(["1) Planificación", "2) Reporte/Confirmación", "3) Registros y Descargas"])

    # -------------------------
    # TAB 1: Planificación
    # -------------------------
    with tab1:
        st.subheader("Planificación (ex ante): ¿Qué instrumento se aplicará, dónde y cuándo?")

        with st.form("form_planificacion", clear_on_submit=True):
            colA, colB, colC = st.columns(3)

            with colA:
                dependencia = st.selectbox("Responsable de Supervisión / Dependencia", DEPENDENCIAS)

                # Instrumentos disponibles por dependencia (dinámico)
                inst_dep = inst_df[inst_df["dependencia_owner"] == dependencia].copy()
                if inst_dep.empty:
                    st.error("No hay instrumentos configurados para esta dependencia. Ajusta el catálogo INSTRUMENTOS.")
                    st.stop()

                tipo_instrumento = st.selectbox("Tipo de instrumento", sorted(inst_dep["tipo_instrumento"].unique()))
                inst_dep2 = inst_dep[inst_dep["tipo_instrumento"] == tipo_instrumento]

                nivel_territorial = st.selectbox("Nivel territorial", sorted(inst_dep2["nivel_territorial"].unique()))
                inst_dep3 = inst_dep2[inst_dep2["nivel_territorial"] == nivel_territorial]

                instrumento_sel = st.selectbox("Instrumento (nombre)", inst_dep3["nombre_instrumento"].tolist())
                row_inst = inst_dep3[inst_dep3["nombre_instrumento"] == instrumento_sel].iloc[0]
                id_instrumento = row_inst["id_instrumento"]
                marco = row_inst["marco_normativo"]

                st.caption(f"ID instrumento: {id_instrumento}")
                st.caption(f"Marco: {marco}")

            with colB:
                anio = st.number_input("Año", min_value=2020, max_value=2100, value=date.today().year, step=1)
                periodo_planificado = st.selectbox("Periodo planificado", PERIODOS)
                tipo_aplicacion = st.selectbox("Tipo de acción (según definiciones del procedimiento)", TIPO_APLICACION)
                fecha_registro = st.date_input("Fecha registro", value=date.today())

            with colC:
                # Territorio dinámico según nivel
                req = territorial_fields_for_level(nivel_territorial)

                region = provincia = comuna = None

                if req["region"]:
                    region = st.selectbox("Región", ["(No aplica)"] + regiones_from_df(divisiones_df))
                    if region == "(No aplica)":
                        region = None

                if req["provincia"]:
                    if not region:
                        st.info("Selecciona una región para habilitar provincia.")
                    else:
                        provs = provincias_for_region(divisiones_df, region)
                        provincia = st.selectbox("Provincia", ["(No aplica)"] + provs)
                        if provincia == "(No aplica)":
                            provincia = None

                if req["comuna"]:
                    if not region or not provincia:
                        st.info("Selecciona región y provincia para habilitar comuna.")
                    else:
                        comms = comunas_for_provincia(divisiones_df, region, provincia)
                        comuna = st.selectbox("Comuna", ["(No aplica)"] + comms)
                        if comuna == "(No aplica)":
                            comuna = None

                responsable = st.text_input("Responsable (nombre)", value="")
                cargo_responsable = st.text_input("Cargo responsable", value="")
                email_responsable = st.text_input("Email responsable (opcional)", value="")

            observaciones = st.text_area("Observaciones", height=110)

            submitted = st.form_submit_button("Guardar planificación")

            if submitted:
                # Validaciones mínimas según aplicabilidad
                if not responsable.strip():
                    st.error("Debes indicar el responsable (nombre).")
                    st.stop()

                # Si nivel exige región/provincia/comuna, debe existir selección
                if req["region"] and not region:
                    st.error("Este nivel exige Región.")
                    st.stop()
                if req["provincia"] and not provincia:
                    st.error("Este nivel exige Provincia.")
                    st.stop()
                if req["comuna"] and not comuna:
                    st.error("Este nivel exige Comuna.")
                    st.stop()

                id_plan = make_id("PLA")
                payload = {
                    "id_planificacion": id_plan,
                    "dependencia": dependencia,
                    "id_instrumento": id_instrumento,
                    "tipo_instrumento": tipo_instrumento,
                    "nombre_instrumento": instrumento_sel,
                    "nivel_territorial": nivel_territorial,
                    "region": region,
                    "provincia": provincia,
                    "comuna": comuna,
                    "anio": int(anio),
                    "periodo_planificado": periodo_planificado,
                    "tipo_aplicacion": tipo_aplicacion,
                    "responsable_planificacion": responsable.strip(),
                    "cargo_responsable_planificacion": cargo_responsable.strip() or None,
                    "email_responsable_planificacion": email_responsable.strip() or None,
                    "fecha_registro": str(fecha_registro),
                    "observaciones": observaciones.strip() or None,
                }
                insert_planificacion(payload)
                st.success(f"Planificación guardada. ID: {id_plan}")

        st.divider()
        st.caption(
            f"Territorio dinámico: para cobertura completa, agrega el archivo {DIVISIONES_PATH} "
            "con columnas region, provincia, comuna."
        )

    # -------------------------
    # TAB 2: Reporte/Confirmación
    # -------------------------
    with tab2:
        st.subheader("Reporte (ex post): Confirmación de ejecución y evidencias")

        colF1, colF2, colF3 = st.columns(3)
        with colF1:
            fil_anio = st.number_input("Filtrar por año", min_value=2020, max_value=2100,
                                       value=date.today().year, step=1, key="f_anio")
        with colF2:
            # Región solo como filtro (no cascada)
            fil_region = st.selectbox("Filtrar por región", ["Todas"] + regiones_from_df(divisiones_df), index=0, key="f_region")
        with colF3:
            fil_dep = st.selectbox("Filtrar por dependencia", ["Todas"] + DEPENDENCIAS, index=0, key="f_dep")

        plan_df = fetch_planificaciones({
            "anio": int(fil_anio),
            "region": fil_region,
            "dependencia": fil_dep,
        })

        if plan_df.empty:
            st.info("No hay planificaciones para los filtros seleccionados.")
        else:
            plan_df["tiene_reporte"] = plan_df["id_planificacion"].apply(has_reporte_for_planificacion)
            show_all = st.checkbox("Mostrar también planificaciones ya reportadas", value=False)
            if not show_all:
                plan_df_view = plan_df[~plan_df["tiene_reporte"]].copy()
            else:
                plan_df_view = plan_df.copy()

            plan_df_view["label"] = plan_df_view.apply(
                lambda r: (
                    f'{r["id_planificacion"]} | {r["dependencia"]} | {r["tipo_instrumento"]} | {r["nivel_territorial"]} | '
                    f'{(r["region"] or "-")} / {(r["provincia"] or "-")} / {(r["comuna"] or "-")} | '
                    f'{r["nombre_instrumento"]} | {r["anio"]} {r["periodo_planificado"]}'
                ),
                axis=1
            )

            sel = st.selectbox("Selecciona una planificación", plan_df_view["label"].tolist())
            id_plan_sel = sel.split(" | ")[0].strip()
            plan_row = fetch_planificacion_by_id(id_plan_sel)

            if plan_row is None:
                st.error("No se encontró la planificación seleccionada.")
            else:
                st.write("**Resumen**")
                st.json({
                    "ID Planificación": plan_row["id_planificacion"],
                    "Dependencia": plan_row["dependencia"],
                    "Instrumento": plan_row["nombre_instrumento"],
                    "Tipo / Nivel": f'{plan_row["tipo_instrumento"]} / {plan_row["nivel_territorial"]}',
                    "Territorio": {
                        "Región": plan_row["region"],
                        "Provincia": plan_row["provincia"],
                        "Comuna": plan_row["comuna"],
                    },
                    "Periodo": f'{plan_row["anio"]} - {plan_row["periodo_planificado"]}',
                    "Tipo acción": plan_row["tipo_aplicacion"],
                    "Responsable planificación": plan_row["responsable_planificacion"],
                })

                st.divider()

                with st.form("form_reporte", clear_on_submit=True):
                    c1, c2, c3 = st.columns(3)

                    with c1:
                        ejecutado = st.selectbox("¿Se ejecutó lo planificado?", ESTADO_EJECUCION)
                        fecha_ejecucion = st.date_input("Fecha de ejecución", value=date.today())
                        tipo_evidencia = st.selectbox("Tipo de evidencia", TIPO_EVIDENCIA)

                    with c2:
                        evidencia_file = st.file_uploader(
                            "Adjuntar evidencia (PDF/Word/Excel/Imagen)",
                            type=["pdf", "doc", "docx", "xls", "xlsx", "png", "jpg", "jpeg"],
                            accept_multiple_files=False
                        )
                        responsable_rep = st.text_input("Responsable reporte (nombre)", value="")
                        cargo_rep = st.text_input("Cargo responsable reporte", value="")

                    with c3:
                        email_rep = st.text_input("Email responsable reporte (opcional)", value="")
                        fecha_reporte = st.date_input("Fecha de reporte", value=date.today())
                        obs_rep = st.text_area("Observaciones", height=110)

                    motivo_no = ""
                    tipo_motivo = ""
                    reprograma = ""

                    if ejecutado in ["No", "Parcial"]:
                        st.markdown("**Justificación (solo si No/Parcial):**")
                        j1, j2, j3 = st.columns([2, 1, 1])
                        with j1:
                            motivo_no = st.text_input("Motivo / explicación", value="")
                        with j2:
                            tipo_motivo = st.selectbox("Tipo de motivo", TIPO_MOTIVO)
                        with j3:
                            reprograma = st.selectbox("¿Se reprogramará?", ["Sí", "No"])

                    submit_rep = st.form_submit_button("Guardar reporte")

                    if submit_rep:
                        if not responsable_rep.strip():
                            st.error("Debes indicar el responsable del reporte (nombre).")
                            st.stop()

                        evidencia_path = save_uploaded_file(evidencia_file) if evidencia_file else ""
                        id_rep = make_id("REP")
                        payload = {
                            "id_reporte": id_rep,
                            "id_planificacion": id_plan_sel,
                            "ejecutado": ejecutado,
                            "fecha_ejecucion": str(fecha_ejecucion),
                            "tipo_evidencia": tipo_evidencia,
                            "evidencia_path": evidencia_path or None,
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
                        st.success(f"Reporte guardado. ID: {id_rep}")

    # -------------------------
    # TAB 3: Registros / Descargas
    # -------------------------
    with tab3:
        st.subheader("Registros y exportación")

        left, right = st.columns(2)

        with left:
            st.write("**Planificaciones**")
            dfp = fetch_planificaciones({"anio": None, "region": "Todas", "dependencia": "Todas"})
            st.dataframe(dfp, use_container_width=True, height=320)
            if not dfp.empty:
                st.download_button(
                    "Descargar planificaciones (CSV)",
                    data=dfp.to_csv(index=False).encode("utf-8"),
                    file_name="planificaciones.csv",
                    mime="text/csv"
                )

        with right:
            st.write("**Reportes**")
            dfr = fetch_reportes()
            st.dataframe(dfr, use_container_width=True, height=320)
            if not dfr.empty:
                st.download_button(
                    "Descargar reportes (CSV)",
                    data=dfr.to_csv(index=False).encode("utf-8"),
                    file_name="reportes.csv",
                    mime="text/csv"
                )

        st.divider()
        st.subheader("Consolidado (Planificación + Reporte)")
        if dfp.empty:
            st.info("No hay planificaciones registradas.")
        else:
            merged = dfp.merge(dfr, on="id_planificacion", how="left", suffixes=("_plan", "_rep"))

            total = len(merged)
            ejecutadas = int((merged["ejecutado"] == "Sí").sum()) if "ejecutado" in merged.columns else 0
            parciales = int((merged["ejecutado"] == "Parcial").sum()) if "ejecutado" in merged.columns else 0
            no_ejec = int((merged["ejecutado"] == "No").sum()) if "ejecutado" in merged.columns else 0
            sin_reporte = int(merged["ejecutado"].isna().sum()) if "ejecutado" in merged.columns else total

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total planificaciones", total)
            m2.metric("Ejecutadas (Sí)", ejecutadas)
            m3.metric("Parciales", parciales)
            m4.metric("Sin reporte", sin_reporte)

            st.dataframe(merged, use_container_width=True, height=360)
            st.download_button(
                "Descargar consolidado (CSV)",
                data=merged.to_csv(index=False).encode("utf-8"),
                file_name="consolidado_planificacion_reporte.csv",
                mime="text/csv"
            )

    st.caption(
        "Nota técnica: La asignación de instrumentos por dependencia y el marco procedimental se fundamentan en el "
        "Procedimiento del Plan Anual de Supervisión. :contentReference[oaicite:5]{index=5}"
    )


if __name__ == "__main__":
    main()
