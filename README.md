# Outdoor decision monitor

Dashboard Streamlit che trasforma i risultati del progetto `outdoor-api-monitor` in una vista operativa per pianificare uscite o riprese outdoor.

## Cosa mostra

- temperatura e probabilità di precipitazione per località e giorno;
- migliore finestra oraria per ogni combinazione località/giorno;
- ore con minore probabilità di pioggia;
- esito, record, durata ed errori delle richieste API;
- esito dell'ultima esecuzione e storico del log.

## Regola di interpretazione

La soglia iniziale è 30% ed è modificabile dalla sidebar. Per ogni località e giorno la dashboard cerca la sequenza continua più lunga di ore con probabilità di precipitazione minore o uguale alla soglia. A parità di durata, sceglie la sequenza con rischio pioggia medio più basso.

La finestra proposta è un supporto decisionale, **non un'allerta meteo**. I CSV usati contengono soltanto temperatura e probabilità di precipitazione: prima di un'uscita occorre verificare anche vento, visibilità, fulmini e condizioni locali.

## File dati

- `data/output/previsioni.csv`: previsioni orari reali acquisite da Open-Meteo il 7 novembre 2026;
- `logs/run_log.csv`: storico delle richieste, compresa la richiesta 400 deliberatamente non valida usata per il test.

## Avvio

Dalla cartella del progetto:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Aprire l'indirizzo locale indicato da Streamlit, normalmente `http://localhost:8501`.

## Test

```bash
python -m unittest -v
```

I test verificano rendering iniziale, filtro per località, soglia pioggia a zero e selezione vuota.
