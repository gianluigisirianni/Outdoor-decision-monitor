from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
FORECAST_PATH = PROJECT_ROOT / "data" / "output" / "previsioni.csv"
LOG_PATH = PROJECT_ROOT / "logs" / "run_log.csv"

st.set_page_config(
    page_title="Outdoor decision monitor",
    page_icon=":material/landscape:",
    layout="wide",
)


@st.cache_data(ttl="1m")
def load_forecasts(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {
        "localita",
        "data",
        "ora",
        "temperatura",
        "probabilita_precipitazione",
    }
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Colonne mancanti nelle previsioni: {sorted(missing)}")

    df["data"] = pd.to_datetime(df["data"], errors="raise")
    df["timestamp"] = pd.to_datetime(
        df["data"].dt.strftime("%Y-%m-%d") + " " + df["ora"], errors="raise"
    )
    df["temperatura"] = pd.to_numeric(df["temperatura"], errors="raise")
    df["probabilita_precipitazione"] = pd.to_numeric(
        df["probabilita_precipitazione"], errors="raise"
    )
    return df.sort_values("timestamp").reset_index(drop=True)


@st.cache_data(ttl="1m")
def load_logs(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {
        "timestamp",
        "localita",
        "status_http",
        "numero_record",
        "durata",
        "esito",
        "errore",
    }
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Colonne mancanti nel log: {sorted(missing)}")

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="raise")
    df["durata"] = pd.to_numeric(df["durata"], errors="coerce")
    df["numero_record"] = pd.to_numeric(df["numero_record"], errors="coerce")
    df["errore"] = df["errore"].fillna("")
    return df.sort_values("timestamp", ascending=False).reset_index(drop=True)


def best_window(group: pd.DataFrame, threshold: int) -> dict[str, object] | None:
    """Return the longest favourable window, breaking ties by lower rain risk."""
    ordered = group.sort_values("timestamp")
    best: list[pd.Series] = []
    current: list[pd.Series] = []

    for _, row in ordered.iterrows():
        if row["probabilita_precipitazione"] <= threshold:
            current.append(row)
        else:
            if len(current) > len(best):
                best = current
            elif len(current) == len(best) and current:
                current_risk = sum(
                    float(item["probabilita_precipitazione"]) for item in current
                )
                best_risk = sum(
                    float(item["probabilita_precipitazione"]) for item in best
                )
                if current_risk < best_risk:
                    best = current
            current = []

    if len(current) > len(best):
        best = current
    elif len(current) == len(best) and current:
        current_risk = sum(
            float(item["probabilita_precipitazione"]) for item in current
        )
        best_risk = sum(float(item["probabilita_precipitazione"]) for item in best)
        if current_risk < best_risk:
            best = current

    if not best:
        return None

    start = pd.Timestamp(best[0]["timestamp"])
    end = pd.Timestamp(best[-1]["timestamp"]) + pd.Timedelta(hours=1)
    return {
        "Località": best[0]["localita"],
        "Giorno": start.strftime("%d/%m/%Y"),
        "Inizio": start.strftime("%H:%M"),
        "Fine": end.strftime("%H:%M"),
        "Durata (ore)": len(best),
        "Temperatura media (°C)": round(
            sum(float(item["temperatura"]) for item in best) / len(best), 1
        ),
        "Pioggia media (%)": round(
            sum(float(item["probabilita_precipitazione"]) for item in best)
            / len(best),
            1,
        ),
    }


def build_best_windows(df: pd.DataFrame, threshold: int) -> pd.DataFrame:
    windows: list[dict[str, object]] = []
    for _, group in df.groupby(["localita", "data"], sort=True):
        window = best_window(group, threshold)
        if window is not None:
            windows.append(window)
    return pd.DataFrame(windows)


st.title("Outdoor decision monitor")
st.caption(
    "Previsioni Open-Meteo e controllo del flusso API: dai dati orari a una "
    "finestra operativa leggibile."
)

if not FORECAST_PATH.exists() or not LOG_PATH.exists():
    st.error(
        "File dati non trovati. Servono `data/output/previsioni.csv` e "
        "`logs/run_log.csv` nella cartella del progetto."
    )
    st.stop()

try:
    forecasts = load_forecasts(str(FORECAST_PATH))
    logs = load_logs(str(LOG_PATH))
except (OSError, ValueError, pd.errors.ParserError) as exc:
    st.error(f"Impossibile leggere i dati: {exc}")
    st.stop()

latest_run = pd.Timestamp(logs["timestamp"].max())
latest_logs = logs[logs["timestamp"] == latest_run].copy()
latest_successes = int((latest_logs["esito"] == "ok").sum())
latest_total = len(latest_logs)
latest_success_rate = latest_successes / latest_total if latest_total else 0

with st.sidebar:
    st.header("Filtri")
    location_options = sorted(forecasts["localita"].unique().tolist())
    selected_locations = st.multiselect(
        "Località",
        options=location_options,
        default=location_options,
        key="locations",
    )
    date_options = sorted(forecasts["data"].dt.date.unique().tolist())
    selected_dates = st.multiselect(
        "Giorni",
        options=date_options,
        default=date_options,
        key="dates",
        format_func=lambda value: value.strftime("%d/%m/%Y"),
    )
    rain_threshold = st.slider(
        "Probabilità massima di pioggia (%)",
        min_value=0,
        max_value=100,
        value=30,
        step=5,
        key="rain_threshold",
    )
    st.caption(
        f"Ultima acquisizione registrata: {latest_run.strftime('%d/%m/%Y %H:%M:%S')}"
    )

filtered = forecasts[
    forecasts["localita"].isin(selected_locations)
    & forecasts["data"].dt.date.isin(selected_dates)
].copy()

if filtered.empty:
    st.warning("Nessun dato disponibile con i filtri selezionati.")
    st.stop()

favourable = filtered[
    filtered["probabilita_precipitazione"] <= rain_threshold
].copy()

with st.container(horizontal=True):
    st.metric("Località selezionate", len(selected_locations), border=True)
    st.metric("Ore entro soglia", len(favourable), border=True)
    st.metric(
        "Temperatura min–max",
        f"{filtered['temperatura'].min():.1f} / {filtered['temperatura'].max():.1f} °C",
        border=True,
    )
    st.metric(
        "Successo ultima esecuzione",
        f"{latest_success_rate:.0%}",
        f"{latest_successes}/{latest_total} richieste",
        border=True,
    )

st.subheader("Migliore finestra per località e giorno")
st.caption(
    f"Un'ora è considerata favorevole quando la probabilità di precipitazione "
    f"è ≤ {rain_threshold}%. A parità di durata viene scelta la finestra con "
    "rischio pioggia medio più basso."
)
windows = build_best_windows(filtered, rain_threshold)
if windows.empty:
    st.warning("Nessuna finestra rispetta la soglia scelta.")
else:
    st.dataframe(
        windows,
        hide_index=True,
        alt="Migliori finestre outdoor per località e giorno",
    )

st.info(
    "La finestra è un supporto per pianificare uscite o riprese, non un'allerta "
    "meteo. Questi CSV contengono soltanto temperatura e probabilità di pioggia: "
    "prima di decidere vanno verificati anche vento, visibilità, fulmini e "
    "condizioni locali.",
    title="Come interpretare il risultato",
)

left, right = st.columns(2)
with left:
    with st.container(border=True):
        st.subheader("Temperatura nel tempo")
        temperature_chart = (
            alt.Chart(filtered)
            .mark_line()
            .encode(  # ty: ignore[unresolved-attribute]
                x=alt.X("timestamp:T", title="Data e ora"),
                y=alt.Y("temperatura:Q", title="Temperatura (°C)"),
                color=alt.Color("localita:N", title="Località"),
                tooltip=[
                    alt.Tooltip("localita:N", title="Località"),
                    alt.Tooltip("timestamp:T", title="Data e ora"),
                    alt.Tooltip("temperatura:Q", title="Temperatura (°C)", format=".1f"),
                ],
            )
        )
        st.altair_chart(
            temperature_chart,
            alt="Andamento della temperatura per le località selezionate",
        )

with right:
    with st.container(border=True):
        st.subheader("Probabilità di precipitazione")
        rain_lines = (
            alt.Chart(filtered)
            .mark_line()
            .encode(  # ty: ignore[unresolved-attribute]
                x=alt.X("timestamp:T", title="Data e ora"),
                y=alt.Y(
                    "probabilita_precipitazione:Q",
                    title="Probabilità (%)",
                    scale=alt.Scale(domain=[0, 100]),
                ),
                color=alt.Color("localita:N", title="Località"),
                tooltip=[
                    alt.Tooltip("localita:N", title="Località"),
                    alt.Tooltip("timestamp:T", title="Data e ora"),
                    alt.Tooltip(
                        "probabilita_precipitazione:Q",
                        title="Pioggia (%)",
                        format=".0f",
                    ),
                ],
            )
        )
        threshold_rule = (
            alt.Chart(pd.DataFrame({"soglia": [rain_threshold]}))
            .mark_rule(strokeDash=[6, 4])
            .encode(y="soglia:Q")  # ty: ignore[unresolved-attribute]
        )
        st.altair_chart(
            rain_lines + threshold_rule,
            alt="Probabilità di pioggia con soglia operativa selezionata",
        )

st.subheader("Le 20 ore con minore probabilità di pioggia")
best_hours = favourable.sort_values(
    ["probabilita_precipitazione", "timestamp", "localita"]
).head(20)
if best_hours.empty:
    st.warning("Nessuna ora rispetta la soglia selezionata.")
else:
    display_hours = best_hours[
        ["localita", "timestamp", "temperatura", "probabilita_precipitazione"]
    ].copy()
    display_hours["timestamp"] = display_hours["timestamp"].dt.strftime(
        "%d/%m/%Y %H:%M"
    )
    display_hours = display_hours.rename(
        columns={
            "localita": "Località",
            "timestamp": "Data e ora",
            "temperatura": "Temperatura (°C)",
            "probabilita_precipitazione": "Pioggia (%)",
        }
    )
    st.dataframe(
        display_hours,
        hide_index=True,
        alt="Ore con la minore probabilità di precipitazione",
    )

st.download_button(
    "Scarica i dati filtrati",
    data=filtered.to_csv(index=False).encode("utf-8"),
    file_name="previsioni_filtrate.csv",
    mime="text/csv",
    key="download_filtered",
)

st.divider()
st.subheader("Salute del flusso API")
if latest_successes == latest_total and latest_total > 0:
    st.success(
        f"Ultima esecuzione: {latest_successes} richieste riuscite su {latest_total}."
    )
else:
    st.warning(
        f"Ultima esecuzione: {latest_successes} richieste riuscite su {latest_total}."
    )

with st.container(horizontal=True):
    st.metric("Record ultima esecuzione", int(latest_logs["numero_record"].sum()), border=True)
    st.metric(
        "Durata media richiesta",
        f"{latest_logs['durata'].mean():.2f} s",
        border=True,
    )
    st.metric(
        "Errori nello storico",
        int((logs["esito"] != "ok").sum()),
        border=True,
    )

st.markdown("**Ultime richieste registrate**")
recent_logs = logs.head(12).copy()
recent_logs["timestamp"] = recent_logs["timestamp"].dt.strftime("%d/%m/%Y %H:%M:%S")
recent_logs = recent_logs.rename(
    columns={
        "timestamp": "Timestamp",
        "localita": "Località",
        "status_http": "HTTP",
        "numero_record": "Record",
        "durata": "Durata (s)",
        "esito": "Esito",
        "errore": "Errore",
    }
)
st.dataframe(
    recent_logs,
    hide_index=True,
    alt="Storico recente delle richieste API",
)

error_logs = logs[logs["esito"] != "ok"]
if not error_logs.empty:
    with st.expander("Dettaglio degli errori storici"):
        st.caption(
            "L'errore 400 presente nello storico appartiene alla richiesta "
            "deliberatamente non valida usata per il test."
        )
        st.dataframe(
            error_logs[["timestamp", "localita", "status_http", "errore"]].rename(
                columns={
                    "timestamp": "Timestamp",
                    "localita": "Località",
                    "status_http": "HTTP",
                    "errore": "Errore",
                }
            ),
            hide_index=True,
            alt="Dettaglio degli errori API registrati",
        )
