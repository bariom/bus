import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import seaborn as sns
import pandas as pd
import json

# Load configuration from JSON file
config_path = './busConfig.json'
with open(config_path, 'r') as f:
    config = json.load(f)

# Extract values from configuration
GIORNI_FERIALI = config["GIORNI_FERIALI"]
GIORNI_WEEKEND = config["GIORNI_WEEKEND"]
ANNI_PROIEZIONE = config["ANNI_PROIEZIONE"]
TASSO_INFLAZIONE_DIESEL = config["TASSO_INFLAZIONE_DIESEL"]
TASSO_INFLAZIONE_ELETTRICO = config["TASSO_INFLAZIONE_ELETTRICO"]
COSTI_UNA_TANTUM = config["COSTI_INFRA_ELETTRICA"]
num_bus_initial = config["NUMERO_BUS"]

giorni_totali = GIORNI_FERIALI + GIORNI_WEEKEND

dati_bus = {
    "elettrico": config["elettrico"],
    "diesel": config["diesel"]
}

def gestione_km_linea(km_feriali, km_weekend, km_limite):
    # Calculate electric and diesel usage for weekdays
    km_elettrico_feriali = min(km_feriali, km_limite) * GIORNI_FERIALI
    km_diesel_extra_feriali = max(0, km_feriali - km_limite) * GIORNI_FERIALI

    # Calculate electric and diesel usage for weekends
    km_elettrico_weekend = min(km_weekend, km_limite) * GIORNI_WEEKEND
    km_diesel_extra_weekend = max(0, km_weekend - km_limite) * GIORNI_WEEKEND

    # Sum up the total kilometers covered by electric and diesel buses
    km_elettrico_totale = km_elettrico_feriali + km_elettrico_weekend
    km_diesel_extra_totale = km_diesel_extra_feriali + km_diesel_extra_weekend

    # Check if any extra diesel bus is needed (1 bus per line exceeding the limit)
    supporto_diesel_needed = int(km_feriali > km_limite) + int(km_weekend > km_limite)

    return km_elettrico_totale, km_diesel_extra_totale, supporto_diesel_needed

def calcola_costo_annuale(km_annui, costo_carburante, consumo_medio, costo_manutenzione, num_bus, ammortamento_annuale,
                          anno, periodo_ammortamento, costo_iniziale_bus):
    costo_carburante_annuo = km_annui * consumo_medio * costo_carburante
    costo_totale = (costo_carburante_annuo + costo_manutenzione + ammortamento_annuale) * num_bus
    if anno % periodo_ammortamento == 0 and anno != 0:
        costo_totale += costo_iniziale_bus * num_bus  # Add the bus purchase cost in the replacement year
    return round(costo_totale, 2)

def calcola_costo_annuale_diesel_supporto(km_diesel_extra, costo_carburante, consumo_medio, costo_manutenzione, ammortamento_annuale, numero_diesel_supporto, include_initial_purchase=False):
    # Calculate the cost associated with the diesel buses based on the actual number needed
    costo_carburante_annuo = km_diesel_extra * consumo_medio * costo_carburante
    costo_totale = (costo_carburante_annuo + costo_manutenzione + ammortamento_annuale) * numero_diesel_supporto
    if include_initial_purchase:
        costo_totale += dati_bus["diesel"]["costo_iniziale"] * numero_diesel_supporto
    return round(costo_totale, 2)

def calcola_costo_per_km(costo_totale, km_annui):
    return round(costo_totale / km_annui, 2) if km_annui != 0 else 0

def calcola_emissioni_co2(km_annui, emissioni_per_unita, num_bus):
    emissioni_totali = (km_annui * emissioni_per_unita * num_bus)
    return round(emissioni_totali, 2)

def calcola_costo_proiezione(km_annui, consumo_medio, costo_manutenzione, costo_iniziale_bus, costo_carburante,
                             tasso_inflazione, anni, periodo_ammortamento, tipo_bus, num_bus, ammortamento=True):
    costi_annuali = []
    ammortamento_annuale = costo_iniziale_bus / periodo_ammortamento
    costo_una_tantum_applicato = False
    for anno in range(anni):
        if ammortamento:
            costo_annuale = calcola_costo_annuale(km_annui, costo_carburante, consumo_medio,
                                                  costo_manutenzione, num_bus, ammortamento_annuale, anno,
                                                  periodo_ammortamento, costo_iniziale_bus)
        else:
            costo_annuale = calcola_costo_annuale(km_annui, costo_carburante, consumo_medio, costo_manutenzione,
                                                  num_bus, ammortamento_annuale, anno, periodo_ammortamento,
                                                  costo_iniziale_bus)

        if anno == 0:
            costo_annuale += costo_iniziale_bus * num_bus  # Include the initial bus purchase cost in the first year
            if tipo_bus == "elettrico" and not costo_una_tantum_applicato:
                costo_annuale += COSTI_UNA_TANTUM
                costo_una_tantum_applicato = True

        costi_annuali.append(costo_annuale)
        costo_carburante *= (1 + tasso_inflazione)
    return costi_annuali

def main():
    st.title("Analisi Comparativa tra Bus Elettrici e Diesel")

    st.sidebar.header("Input dell'utente")

    # Add functionality to increase or decrease the number of buses
    num_bus = st.sidebar.number_input("Numero di bus", min_value=1, max_value=100, value=num_bus_initial, step=1)

    km_feriali_linee = [
        st.sidebar.number_input(f"Inserire i km giornalieri percorsi durante i giorni feriali per la linea {i + 1}:",
                                value=100.0, step=5.0) for i in range(num_bus)]
    km_weekend_linee = [
        st.sidebar.number_input(f"Inserire i km giornalieri percorsi durante il weekend per la linea {i + 1}:",
                                value=50.0, step=5.0) for i in range(num_bus)]

    km_totali = {"elettrico": 0, "diesel_extra": 0}
    total_supporto_diesel_needed = 0

    for km_feriali, km_weekend in zip(km_feriali_linee, km_weekend_linee):
        km_elettrico, km_diesel_extra, supporto_diesel_needed = gestione_km_linea(km_feriali, km_weekend,
                                                                                  dati_bus["elettrico"]["km_limite"])
        km_totali["elettrico"] += km_elettrico
        km_totali["diesel_extra"] += km_diesel_extra
        total_supporto_diesel_needed += supporto_diesel_needed

    ammortamento_annuale_elettrico = (dati_bus["elettrico"]["costo_iniziale"] - dati_bus["elettrico"]["bonus"]) / \
                                     dati_bus["elettrico"]["periodo_ammortamento"]
    ammortamento_annuale_diesel = (dati_bus["diesel"]["costo_iniziale"] - dati_bus["diesel"]["bonus"]) / \
                                  dati_bus["diesel"]["periodo_ammortamento"]

    # Calculate costs and emissions for the baseline scenario with only diesel buses
    km_totali_diesel_completo = sum(km_feriali_linee) * GIORNI_FERIALI + sum(km_weekend_linee) * GIORNI_WEEKEND

    costo_annuale_diesel_completo = calcola_costo_annuale(km_totali_diesel_completo,
                                                          dati_bus["diesel"]["costo_carburante"],
                                                          dati_bus["diesel"]["consumo"],
                                                          dati_bus["diesel"]["costo_manutenzione"], num_bus,
                                                          ammortamento_annuale_diesel, 0,
                                                          dati_bus["diesel"]["periodo_ammortamento"],
                                                          dati_bus["diesel"]["costo_iniziale"])

    emissioni_annue_diesel_completo = calcola_emissioni_co2(km_totali_diesel_completo,
                                                            dati_bus["diesel"]["emissioni"], num_bus)

    # Calculate costs and emissions for electric buses and diesel support (if needed)
    costo_annuale_elettrico = calcola_costo_annuale(km_totali["elettrico"], dati_bus["elettrico"]["costo_carburante"],
                                                    dati_bus["elettrico"]["consumo"],
                                                    dati_bus["elettrico"]["costo_manutenzione"], num_bus,
                                                    ammortamento_annuale_elettrico, 0,
                                                    dati_bus["elettrico"]["periodo_ammortamento"],
                                                    dati_bus["elettrico"]["costo_iniziale"])
    emissioni_annue_elettrico = calcola_emissioni_co2(km_totali["elettrico"], dati_bus["elettrico"]["emissioni"],
                                                      num_bus)

    # Include initial purchase cost of additional diesel buses only if needed
    costo_annuale_diesel_supporto = calcola_costo_annuale_diesel_supporto(km_totali["diesel_extra"],
                                                                          dati_bus["diesel"]["costo_carburante"],
                                                                          dati_bus["diesel"]["consumo"],
                                                                          dati_bus["diesel"]["costo_manutenzione"],
                                                                          ammortamento_annuale_diesel,
                                                                          total_supporto_diesel_needed,
                                                                          include_initial_purchase=True)

    emissioni_annue_diesel_extra = calcola_emissioni_co2(km_totali["diesel_extra"], dati_bus["diesel"]["emissioni"],
                                                         total_supporto_diesel_needed)

    # Calculate cost per km for electric bus
    costo_per_km_elettrico = calcola_costo_per_km(costo_annuale_elettrico, km_totali["elettrico"])

    # Calculate cost per km for diesel support bus
    costo_per_km_diesel_supporto = calcola_costo_per_km(costo_annuale_diesel_supporto, km_totali["diesel_extra"])

    # Calculate emissions per km for electric bus
    emissioni_per_km_elettrico = calcola_costo_per_km(emissioni_annue_elettrico, km_totali["elettrico"])

    # Calculate emissions per km for diesel support bus
    emissioni_per_km_diesel_extra = calcola_costo_per_km(emissioni_annue_diesel_extra, km_totali["diesel_extra"])

    # Calculate projections for diesel and electric buses over the specified number of years
    proiezione_costi_diesel = calcola_costo_proiezione(km_totali_diesel_completo,
                                                       dati_bus["diesel"]["consumo"],
                                                       dati_bus["diesel"]["costo_manutenzione"],
                                                       dati_bus["diesel"]["costo_iniziale"] - dati_bus["diesel"][
                                                           "bonus"], dati_bus["diesel"]["costo_carburante"],
                                                       TASSO_INFLAZIONE_DIESEL, ANNI_PROIEZIONE,
                                                       dati_bus["diesel"]["periodo_ammortamento"], tipo_bus="diesel",
                                                       num_bus=num_bus, ammortamento=False)
    proiezione_costi_elettrico = calcola_costo_proiezione(km_totali["elettrico"], dati_bus["elettrico"]["consumo"],
                                                          dati_bus["elettrico"]["costo_manutenzione"],
                                                          dati_bus["elettrico"]["costo_iniziale"] -
                                                          dati_bus["elettrico"]["bonus"],
                                                          dati_bus["elettrico"]["costo_carburante"],
                                                          TASSO_INFLAZIONE_ELETTRICO, ANNI_PROIEZIONE,
                                                          dati_bus["elettrico"]["periodo_ammortamento"],
                                                          tipo_bus="elettrico", num_bus=num_bus, ammortamento=False)

    # Calculate cumulative costs for diesel and electric buses
    costo_cumulato_diesel = np.cumsum(proiezione_costi_diesel)
    costo_cumulato_elettrico = np.cumsum(proiezione_costi_elettrico)

    risparmio_costi_annuale = round(
        costo_annuale_diesel_completo - (costo_annuale_elettrico + costo_annuale_diesel_supporto), 2)
    riduzione_emissioni_annuale = round(
        emissioni_annue_diesel_completo - (emissioni_annue_elettrico + emissioni_annue_diesel_extra), 2)

    percentuale_utilizzo_elettrico = round((km_totali["elettrico"] / sum(km_totali.values())) * 100, 2) if sum(
        km_totali.values()) != 0 else 0
    percentuale_utilizzo_diesel_extra = round((km_totali["diesel_extra"] / sum(km_totali.values())) * 100, 2) if sum(
        km_totali.values()) != 0 else 0

    # Display the results
    st.header("Risultati delle Proiezioni")

    st.subheader("Proiezione Costi Annuali")
    st.markdown(f"""
    - **Bus solo diesel per {ANNI_PROIEZIONE} anni:** {proiezione_costi_diesel}
    - **Bus elettrici per {ANNI_PROIEZIONE} anni:** {proiezione_costi_elettrico}
    """)

    st.subheader("Costi ed Emissioni Attuali")
    st.markdown(f"""
    - **Costo annuale totale per bus elettrici + bus diesel di supporto:** {round(costo_annuale_elettrico + costo_annuale_diesel_supporto, 2)} CHF
    - **Emissioni annuali totali di CO2 per bus elettrici + bus diesel di supporto:** {round(emissioni_annue_elettrico + emissioni_annue_diesel_extra, 2) / 1000} t
    - **Costo annuale totale per bus solo diesel:** {costo_annuale_diesel_completo} CHF
    - **Emissioni annuali totali di CO2 per bus solo diesel:** {emissioni_annue_diesel_completo / 1000} t
    """)

    st.subheader("Costi per km")
    st.markdown(f"""
    - **Bus elettrici:** {costo_per_km_elettrico:.2f} CHF/km
    - **Bus diesel di supporto:** {costo_per_km_diesel_supporto:.2f} CHF/km
    """)

    st.subheader("Emissioni di CO2 per km")
    st.markdown(f"""
    - **Bus elettrici:** {emissioni_per_km_elettrico:.2f} kg/km
    - **Bus diesel di supporto:** {emissioni_per_km_diesel_extra:.2f} kg/km
    """)

    st.subheader("Risparmio Annuale e Riduzione Emissioni")
    st.markdown(f"""
    - **Risparmio annuale in costi utilizzando bus elettrici:** {risparmio_costi_annuale:.2f} CHF
    - **Riduzione annuale delle emissioni di CO2 utilizzando bus elettrici:** {riduzione_emissioni_annuale:.2f} kg
    """)

    st.subheader("Percentuale di Utilizzo dei km Annui")
    st.markdown(f"""
    - **Bus elettrici:** {percentuale_utilizzo_elettrico:.2f}%
    - **Bus diesel di supporto:** {percentuale_utilizzo_diesel_extra:.2f}%
    """)

    # Create comparison graphs
    sns.set(style="whitegrid", palette="deep", font_scale=1.2)

    fig, axs = plt.subplots(3, 2, figsize=(14, 12))
    fig.suptitle(f'Analisi Comparativa tra {num_bus} Bus Elettrici e Diesel', fontsize=20, fontweight='bold')

    anni = np.arange(1, ANNI_PROIEZIONE + 1)
    sns.lineplot(ax=axs[0, 0], x=anni, y=proiezione_costi_diesel, marker='o', label="Costi Bus Diesel", color='green')
    sns.lineplot(ax=axs[0, 0], x=anni, y=proiezione_costi_elettrico, marker='o', label="Costi Bus Elettrici",
                 color='blue')
    axs[0, 0].set_xlabel("", fontsize=14, fontweight='bold')
    axs[0, 0].set_ylabel("Costi annuali (CHF)", fontsize=14, fontweight='bold')
    axs[0, 0].set_title(f"Proiezione dei costi annuali per {ANNI_PROIEZIONE} anni", fontsize=16)
    axs[0, 0].legend()
    axs[0, 0].grid(True)
    axs[0, 0].set_xticks(anni)

    axs[0, 0].yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, pos: f'{int(x):,}'))

    emissioni_annue_totali_elettrico_diesel = emissioni_annue_elettrico + emissioni_annue_diesel_extra
    emissioni_annue_totali_diesel = emissioni_annue_diesel_completo

    emissioni_data = pd.DataFrame({
        'Tipo': ["Elettrici + Diesel di Supporto", "Solo Diesel"],
        'Emissioni': [emissioni_annue_totali_elettrico_diesel / 1000, emissioni_annue_totali_diesel / 1000]
    })
    sns.barplot(ax=axs[0, 1], x='Tipo', y='Emissioni', data=emissioni_data, palette=['blue', 'green'], dodge=False,
                legend=False)
    axs[0, 1].set_ylabel("Emissioni annuali di CO2 (t)", fontsize=14, fontweight='bold')
    axs[0, 1].set_title("Emissioni annuali totali di CO2 in tonnellate", fontsize=16)
    axs[0, 1].grid(True)
    axs[0, 1].set_xlabel('')
    axs[0, 1].tick_params(axis='x', which='both', length=0)

    costi_per_km_data = pd.DataFrame({
        'Tipo': ["Elettrici", "Diesel di Supporto", "Solo Diesel"],
        'Costi per km': [costo_per_km_elettrico, costo_per_km_diesel_supporto, calcola_costo_per_km(costo_annuale_diesel_completo, km_totali_diesel_completo)]
    })
    sns.barplot(ax=axs[1, 0], x='Tipo', y='Costi per km', data=costi_per_km_data, palette=['blue', 'orange', 'green'],
                dodge=False, legend=False)
    axs[1, 0].set_ylabel("Costi per km (CHF)", fontsize=14, fontweight='bold')
    axs[1, 0].set_title(f"Costi per km {num_bus} bus", fontsize=16)
    axs[1, 0].grid(True)
    axs[1, 0].set_xlabel('')
    axs[1, 0].tick_params(axis='x', which='both', length=0)

    emissioni_per_km_data = pd.DataFrame({
        'Tipo': ["Elettrici", "Diesel di Supporto", "Solo Diesel"],
        'Emissioni per km': [emissioni_per_km_elettrico, emissioni_per_km_diesel_extra, calcola_costo_per_km(emissioni_annue_diesel_completo, km_totali_diesel_completo)]
    })
    sns.barplot(ax=axs[1, 1], x='Tipo', y='Emissioni per km', data=emissioni_per_km_data,
                palette=['blue', 'orange', 'green'], dodge=False, legend=False)
    axs[1, 1].set_ylabel("Emissioni di CO2 per km (kg)", fontsize=14, fontweight='bold')
    axs[1, 1].set_title(f"Emissioni di CO2 per km", fontsize=16)
    axs[1, 1].grid(True)
    axs[1, 1].set_xlabel('')
    axs[1, 1].tick_params(axis='x', which='both', length=0)

    sns.lineplot(ax=axs[2, 0], x=anni, y=costo_cumulato_diesel, marker='o', label="Costo Cumulato Diesel",
                 color='green')
    sns.lineplot(ax=axs[2, 0], x=anni, y=costo_cumulato_elettrico, marker='o', label="Costo Cumulato Elettrico",
                 color='blue')
    axs[2, 0].set_xlabel("", fontsize=14, fontweight='bold')
    axs[2, 0].set_ylabel("Costo Cumulato (CHF)", fontsize=14, fontweight='bold')
    axs[2, 0].set_title(f"Costo Cumulato per {ANNI_PROIEZIONE} anni", fontsize=16)
    axs[2, 0].legend()
    axs[2, 0].grid(True)
    axs[2, 0].set_xticks(anni)

    axs[2, 0].yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, pos: f'{x / 1e6:.1f}M'))

    emissioni_totali = [emissioni_annue_elettrico, emissioni_annue_diesel_extra, emissioni_annue_diesel_completo]
    labels = ["Elettrici", "Diesel di Supporto", "Solo Diesel"]
    colors = ['blue', 'orange', 'green']

    axs[2, 1].pie(emissioni_totali, labels=labels, colors=colors, autopct='%1.1f%%', startangle=140,
                  wedgeprops=dict(width=0.3))
    axs[2, 1].set_title("Ripartizione delle Emissioni Totali di CO2", fontsize=16)
    axs[2, 1].axis('equal')

    plt.subplots_adjust(hspace=1)
    fig.tight_layout(rect=[0, 0.03, 1, 0.95])

    st.pyplot(fig)


if __name__ == "__main__":
    main()
