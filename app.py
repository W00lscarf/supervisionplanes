# app.py
import os
import sqlite3
from datetime import date, datetime
from typing import Dict, List, Tuple, Optional

import pandas as pd
import streamlit as st

APP_TITLE = "Supervisión de Instrumentos RRD: Planificación y Reporte"
DB_PATH = "rrd_supervision.db"
UPLOAD_DIR = "uploads"

# -----------------------------
# Catálogos (ajustables)
# -----------------------------
INSTRUMENTOS = [
    # id, tipo, nombre, nivel_territorial, marco
    ("RRD-NAC-001", "RRD", "Plan Estratégico Nacional para la RRD", "Nacional", "Ley 21.364 / D.S. 86/2023 / Procedimiento Supervisión"),
    ("EME-NAC-001", "Emergencia", "Plan Nacional de Emergencia", "Nacional", "Ley 21.364 / D.S. 86/2023 / Procedimiento Supervisión"),
    ("RRD-REG-001", "RRD", "Plan Regional para la RRD", "Regional", "Ley 21.364 / D.S. 86/2023 / Procedimiento Supervisión"),
    ("EME-REG-001", "Emergencia", "Plan Regional de Emergencia", "Regional", "Ley 21.364 / D.S. 86/2023 / Procedimiento Supervisión"),
    ("EME-PRO-001", "Emergencia", "Plan Provincial de Emergencia", "Provincial", "Ley 21.364 / D.S. 86/2023 / Procedimiento Supervisión"),
    ("RRD-COM-001", "RRD", "Plan Comunal para la RRD", "Comunal", "Ley 21.364 / D.S. 86/2023 / Procedimiento Supervisión"),
    ("EME-COM-001", "Emergencia", "Plan Comunal de Emergencia", "Comunal", "Ley 21.364 / D.S. 86/2023 / Procedimiento Supervisión"),
    ("SEC-SEC-001", "Sectorial GRD", "Plan Sectorial GRD", "Sectorial", "Ley 21.364 / D.S. 86/2023 / Procedimiento Supervisión"),
]

REGIONES_CHILE = [
    "Arica y Parinacota","Tarapacá","Antofagasta","Atacama","Coquimbo","Valparaíso",
    "Metropolitana","O’Higgins","Maule","Ñuble","Biobío","La Araucanía","Los Ríos",
    "Los Lagos","Aysén","Magallanes"
]

PERIODOS = ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre",
            "1° Trimestre","2° Trimestre","3° Trimestre","4° Trimestre","1° Semestre","2° Semestre","Anual"]

TIPO_APLICACION = ["Supervisión", "Actualización", "Simulacro", "Difusión", "Otro"]

TIPO_EVIDENCIA = ["Acta", "Informe", "Resolución/Decreto", "Registro fotográfico", "Lista asistencia", "Otro"]

ESTADO_EJECUCION = ["Sí", "No", "Parcial"]

TIPO_MOTIVO = ["Operativo", "Presupuestario", "Normativo", "Fuerza mayor", "Otro"]


# -----------------------------
# DB helpers
# -----------------------------
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
        marco_normativo TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS planificaciones (
        id_planificacion TEXT PRIMARY KEY,
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

    # Upsert catálogo instrumentos
    cur.executemany("""
    INSERT OR REPLACE INTO instrumentos
    (id_instrumento, tipo_instrumento, nombre_instrumento, nivel_territorial, marco_normativo)
    VALUES (?, ?, ?, ?, ?)
    """, INSTRUMENTOS)
    conn.commit()
    conn.close()

def fetch_instrumentos() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM instrumentos ORDER BY tipo_instrumento, nivel_territorial, nombre_instrumento", conn)
    conn.close()
    return df

def insert_planificacion(payload: Dict):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO planificaciones (
        id_planificacion, id_instrumento, tipo_instrumento, nombre_instrumento, nivel_territorial,
        region, provincia, comuna, anio, periodo_planificado, tipo_aplicacion,
        responsable_planificacion, cargo_responsable_planificacion, email_responsable_planificacion,
        fecha_registro, observaciones
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        payload["id_planificacion"], payload["id_instrumento"], payload["tipo_instrumento"], payload["nombre_instrumento"],
        payload["nivel_territorial"], payload["region"], payload["provincia"], payload["comuna"], payload["anio"],
        payload["periodo_planificado"], payload["tipo_aplicacion"], payload["responsable_planificacion"],
        payload["cargo_responsable_planificacion"], payload["email_responsable_planificacion"],
        payload["fecha_registro"], payload["observaciones"]
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
    if filters.get("tipo_instrumento") and filters["tipo_instrumento"] != "Todos":
        query += " AND tipo_instrumento = ?"
        params.append(filters["tipo_instrumento"])
    if filters.get("nivel_territorial") and filters["nivel_territorial"] != "Todos":
        query += " AND nivel_territorial = ?"
        params.append(filters["nivel_territorial"])

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
    # Ej: PLA-20260107-153012-1234
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


# -----------------------------
# UI
# -----------------------------
def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)

    ensure_dirs()
    init_db()

    inst_df = fetch_instrumentos()
    tipos = ["Todos"] + sorted(inst_df["tipo_instrumento"].unique().tolist())
    niveles = ["Todos"] + sorted(inst_df["nivel_territorial"].unique().tolist())

    tab1, tab2, tab3 = st.tabs(["1) Planificación", "2) Reporte/Confirmación", "3) Registros y Descargas"])

    # -------------------------
    # TAB 1: Planificación
    # -------------------------
    with tab1:
        st.subheader("Planificación de aplicación de instrumento")

        with st.form("form_planificacion", clear_on_submit=True):
            colA, colB, colC = st.columns(3)

            with colA:
                tipo_instrumento = st.selectbox("Tipo de instrumento", sorted(inst_df["tipo_instrumento"].unique()))
                nivel_territorial = st.selectbox(
                    "Nivel territorial",
                    sorted(inst_df[inst_df["tipo_instrumento"] == tipo_instrumento]["nivel_territorial"].unique())
                )

                subset = inst_df[
                    (inst_df["tipo_instrumento"] == tipo_instrumento) &
                    (inst_df["nivel_territorial"] == nivel_territorial)
                ].copy()
                instrumento_label = subset["nombre_instrumento"].tolist()
                instrumento_sel = st.selectbox("Instrumento (nombre)", instrumento_label)

                id_instrumento = subset[subset["nombre_instrumento"] == instrumento_sel]["id_instrumento"].iloc[0]
                marco = subset[subset["nombre_instrumento"] == instrumento_sel]["marco_normativo"].iloc[0]
                st.caption(f"ID instrumento: {id_instrumento}")
                st.caption(f"Marco: {marco}")

            with colB:
                anio = st.number_input("Año", min_value=2020, max_value=2100, value=date.today().year, step=1)
                periodo_planificado = st.selectbox("Periodo planificado", PERIODOS)
                tipo_aplicacion = st.selectbox("Tipo de aplicación", TIPO_APLICACION)
                fecha_registro = st.date_input("Fecha registro", value=date.today())

            with colC:
                region = st.selectbox("Región", ["(No aplica)"] + REGIONES_CHILE)

                provincia = st.text_input("Provincia (si aplica)", value="")
                comuna = st.text_input("Comuna (si aplica)", value="")

                responsable = st.text_input("Responsable (nombre)", value="")
                cargo_responsable = st.text_input("Cargo responsable", value="")
                email_responsable = st.text_input("Email responsable (opcional)", value="")

            observaciones = st.text_area("Observaciones", height=120)

            submitted = st.form_submit_button("Guardar planificación")

            if submitted:
                # Validaciones mínimas
                if not responsable.strip():
                    st.error("Debes indicar el responsable (nombre).")
                elif region != "(No aplica)" and not region.strip():
                    st.error("Debes indicar región o marcar (No aplica).")
                else:
                    id_plan = make_id("PLA")
                    payload = {
                        "id_planificacion": id_plan,
                        "id_instrumento": id_instrumento,
                        "tipo_instrumento": tipo_instrumento,
                        "nombre_instrumento": instrumento_sel,
                        "nivel_territorial": nivel_territorial,
                        "region": None if region == "(No aplica)" else region,
                        "provincia": provincia.strip() or None,
                        "comuna": comuna.strip() or None,
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
        st.caption("Sugerencia operativa: usar Provincia/Comuna solo cuando el nivel territorial lo requiera; si no aplica, dejar en blanco.")

    # -------------------------
    # TAB 2: Reporte/Confirmación
    # -------------------------
    with tab2:
        st.subheader("Reporte / Confirmación de ejecución de lo planificado")

        colF1, colF2, colF3 = st.columns(3)
        with colF1:
            fil_anio = st.number_input("Filtrar por año", min_value=2020, max_value=2100, value=date.today().year, step=1, key="f_anio")
        with colF2:
            fil_region = st.selectbox("Filtrar por región", ["Todas"] + REGIONES_CHILE, index=0, key="f_region")
        with colF3:
            fil_tipo = st.selectbox("Filtrar por tipo instrumento", ["Todos"] + sorted(inst_df["tipo_instrumento"].unique()), index=0, key="f_tipo")

        plan_df = fetch_planificaciones({
            "anio": int(fil_anio),
            "region": fil_region,
            "tipo_instrumento": fil_tipo,
            "nivel_territorial": "Todos",
        })

        if plan_df.empty:
            st.info("No hay planificaciones para los filtros seleccionados.")
        else:
            # Mostrar sólo pendientes (sin reporte) por defecto
            plan_df["tiene_reporte"] = plan_df["id_planificacion"].apply(has_reporte_for_planificacion)
            show_all = st.checkbox("Mostrar también planificaciones ya reportadas", value=False)
            if not show_all:
                plan_df_view = plan_df[~plan_df["tiene_reporte"]].copy()
            else:
                plan_df_view = plan_df.copy()

            plan_df_view["label"] = plan_df_view.apply(
                lambda r: f'{r["id_planificacion"]} | {r["tipo_instrumento"]} | {r["nivel_territorial"]} | {r["region"] or "-"} | {r["nombre_instrumento"]} | {r["periodo_planificado"]}',
                axis=1
            )

            sel = st.selectbox("Selecciona una planificación", plan_df_view["label"].tolist())

            id_plan_sel = sel.split(" | ")[0].strip()
            plan_row = fetch_planificacion_by_id(id_plan_sel)

            if plan_row is None:
                st.error("No se encontró la planificación seleccionada.")
            else:
                st.write("**Resumen planificación seleccionada**")
                st.json({
                    "ID Planificación": plan_row["id_planificacion"],
                    "Instrumento": plan_row["nombre_instrumento"],
                    "Tipo / Nivel": f'{plan_row["tipo_instrumento"]} / {plan_row["nivel_territorial"]}',
                    "Territorio": {
                        "Región": plan_row["region"],
                        "Provincia": plan_row["provincia"],
                        "Comuna": plan_row["comuna"],
                    },
                    "Periodo": f'{plan_row["anio"]} - {plan_row["periodo_planificado"]}',
                    "Tipo aplicación": plan_row["tipo_aplicacion"],
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
                        obs_rep = st.text_area("Observaciones", height=120)

                    motivo_no = ""
                    tipo_motivo = ""
                    reprograma = ""

                    if ejecutado in ["No", "Parcial"]:
                        st.markdown("**Justificación (solo si No/Parcial):**")
                        colJ1, colJ2, colJ3 = st.columns([2, 1, 1])
                        with colJ1:
                            motivo_no = st.text_input("Motivo / explicación", value="")
                        with colJ2:
                            tipo_motivo = st.selectbox("Tipo de motivo", TIPO_MOTIVO)
                        with colJ3:
                            reprograma = st.selectbox("¿Se reprogramará?", ["Sí", "No"])

                    submit_rep = st.form_submit_button("Guardar reporte")

                    if submit_rep:
                        if not responsable_rep.strip():
                            st.error("Debes indicar el responsable del reporte (nombre).")
                        else:
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
        st.subheader("Registros")

        colR1, colR2 = st.columns(2)
        with colR1:
            st.write("**Planificaciones**")
            dfp = fetch_planificaciones({"anio": None, "region": "Todas", "tipo_instrumento": "Todos", "nivel_territorial": "Todos"})
            st.dataframe(dfp, use_container_width=True, height=320)
            if not dfp.empty:
                st.download_button(
                    "Descargar planificaciones (CSV)",
                    data=dfp.to_csv(index=False).encode("utf-8"),
                    file_name="planificaciones.csv",
                    mime="text/csv"
                )

        with colR2:
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
            if dfr.empty:
                merged = dfp.copy()
                merged["ejecutado"] = None
            else:
                merged = dfp.merge(dfr, on="id_planificacion", how="left", suffixes=("_plan", "_rep"))

            # Métricas simples
            total = len(merged)
            ejecutadas = int((merged["ejecutado"] == "Sí").sum()) if "ejecutado" in merged.columns else 0
            parciales = int((merged["ejecutado"] == "Parcial").sum()) if "ejecutado" in merged.columns else 0
            no_ejec = int((merged["ejecutado"] == "No").sum()) if "ejecutado" in merged.columns else 0
            sin_reporte = int(merged["ejecutado"].isna().sum()) if "ejecutado" in merged.columns else total

            cM1, cM2, cM3, cM4 = st.columns(4)
            cM1.metric("Total planificaciones", total)
            cM2.metric("Ejecutadas (Sí)", ejecutadas)
            cM3.metric("Parciales", parciales)
            cM4.metric("Sin reporte", sin_reporte)

            st.dataframe(merged, use_container_width=True, height=360)

            st.download_button(
                "Descargar consolidado (CSV)",
                data=merged.to_csv(index=False).encode("utf-8"),
                file_name="consolidado_planificacion_reporte.csv",
                mime="text/csv"
            )

    st.caption("Persistencia: SQLite local. Adjuntos: carpeta uploads/. Para despliegue institucional, migra a PostgreSQL/SQL Server y repositorio documental (SharePoint/S3).")


if __name__ == "__main__":
    main()
