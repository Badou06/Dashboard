import streamlit as st
import pandas as pd
import plotly.express as px
import os

# ==============================================================================
# 1. CONFIGURATION DE L'APPLICATION
# ==============================================================================
st.set_page_config(
    page_title="Analyse Qualité de Service RATP/IDFM",
    page_icon="🚇",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# 2. FONCTIONS DE PRÉPARATION DES DONNÉES
# ==============================================================================

@st.cache_data
def charger_donnees():
    """
    Charge les données depuis le fichier CSV local.
    Gère les encodages et les séparateurs spécifiques.
    """
    # Nom exact du fichier dans votre environnement
    fichier = "indicateurs-qualite-service-parcours-voyageur.csv"
    
    if not os.path.exists(fichier):
        st.error(f"❌ Le fichier '{fichier}' est introuvable. Assurez-vous qu'il est bien téléversé.")
        return None

    # Tentative 1 : Format Excel français (point-virgule + latin-1)
    try:
        df = pd.read_csv(fichier, sep=';', encoding='latin-1', on_bad_lines='skip')
        return df
    except Exception:
        pass

    # Tentative 2 : Format UTF-8
    try:
        df = pd.read_csv(fichier, sep=';', encoding='utf-8', on_bad_lines='skip')
        return df
    except Exception as e:
        st.error(f"Erreur critique lors de la lecture du fichier : {e}")
        return None

def nettoyer_donnees(df):
    """
    Nettoie le DataFrame : renommage, conversion de types, gestion des valeurs manquantes.
    """
    # 1. Standardisation des noms de colonnes (minuscules, sans espaces)
    df.columns = df.columns.str.strip().str.lower()
    
    # 2. Renommage pour plus de clarté (Mapping basé sur le fichier CSV IDFM)
    rename_map = {
        'resultat_indicateurs_en': 'valeur_reelle',
        'objectif_reference_contrat': 'valeur_objectif',
        'ligne': 'ligne',
        'mode': 'mode',
        'thematique': 'thematique',
        'indicateur': 'indicateur',
        'annee': 'annee',
        'trimestre': 'trimestre'
    }
    # On applique le renommage uniquement sur les colonnes trouvées
    df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)
    
    # 3. Conversion des colonnes numériques
    # Gestion des virgules (ex: "98,5" devient 98.5) si c'est du texte
    cols_numeriques = ['valeur_reelle', 'valeur_objectif']
    for col in cols_numeriques:
        if col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].astype(str).str.replace(',', '.', regex=False)
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # 4. Création de variables dérivées pour l'analyse temporelle
    # Création d'un label "Période" (ex: 2023 - T1)
    if 'annee' in df.columns and 'trimestre' in df.columns:
        df['periode_label'] = df['annee'].astype(str) + " - " + df['trimestre'].astype(str)
        
        # Création d'une clé de tri numérique (20231, 20232...) pour que les graphiques soient dans l'ordre
        mapping_trimestre = {'T1': 1, 'T2': 2, 'T3': 3, 'T4': 4}
        # On gère le cas où trimestre serait NaN
        trim_num = df['trimestre'].map(mapping_trimestre).fillna(0)
        df['sort_key'] = df['annee'] * 10 + trim_num
    
    # 5. Suppression des lignes vides ou inutiles (sans résultat)
    if 'valeur_reelle' in df.columns:
        df.dropna(subset=['valeur_reelle'], inplace=True)
    
    return df

# ==============================================================================
# 3. INTERFACE UTILISATEUR (MAIN)
# ==============================================================================

def main():
    # --- A. En-tête ---
    st.title("📊 Dashboard Qualité de Service & Régularité")
    st.markdown("""
    Ce tableau de bord analyse la performance des transports (Métro, RER, Bus, Tram) 
    en comparant les résultats réels aux objectifs contractuels (Données IDFM/RATP).
    """)
    st.divider()

    # --- B. Chargement & Nettoyage ---
    df_raw = charger_donnees()
    if df_raw is None:
        st.stop()
        
    df = nettoyer_donnees(df_raw)
    
    if df.empty:
        st.warning("⚠️ Le fichier a été chargé mais ne contient aucune donnée exploitable après nettoyage.")
        st.stop()

    # --- C. Sidebar (Filtres) ---
    st.sidebar.header("🔍 Filtres")

    # Filtre 1 : Année
    if 'annee' in df.columns:
        annees_dispo = sorted(df['annee'].unique())
        annees_sel = st.sidebar.multiselect("Année(s)", annees_dispo, default=annees_dispo)
        if annees_sel:
            df = df[df['annee'].isin(annees_sel)]

    # Filtre 2 : Mode de transport
    if 'mode' in df.columns:
        # Conversion en string pour éviter crash si NaN
        modes_dispo = ['Tous'] + sorted(df['mode'].dropna().astype(str).unique())
        mode_sel = st.sidebar.selectbox("Mode de transport", modes_dispo)
        if mode_sel != 'Tous':
            df = df[df['mode'] == mode_sel]

    # Filtre 3 : Thématique
    if 'thematique' in df.columns:
        themes_dispo = ['Toutes'] + sorted(df['thematique'].dropna().astype(str).unique())
        theme_sel = st.sidebar.selectbox("Thématique", themes_dispo)
        if theme_sel != 'Toutes':
            df = df[df['thematique'] == theme_sel]

    # --- D. KPIs (Indicateurs Clés) ---
    st.subheader("📈 Performance Globale")
    
    kpi1, kpi2, kpi3 = st.columns(3)
    
    # Initialisation des variables
    moyenne_reelle = 0
    moyenne_objectif = 0
    
    if 'valeur_reelle' in df.columns:
        moyenne_reelle = df['valeur_reelle'].mean()
        kpi1.metric("Taux de Réussite Moyen", f"{moyenne_reelle:.2f} %")
        
    if 'valeur_objectif' in df.columns:
        moyenne_objectif = df['valeur_objectif'].mean()
        kpi2.metric("Objectif Contractuel Moyen", f"{moyenne_objectif:.2f} %")
        
    if 'valeur_reelle' in df.columns and 'valeur_objectif' in df.columns:
        delta = moyenne_reelle - moyenne_objectif
        kpi3.metric("Écart à l'Objectif", f"{delta:.2f} pts", 
                    delta=f"{delta:.2f}", delta_color="normal")

    st.divider()

    # --- E. Visualisations ---
    
    col_left, col_right = st.columns(2)

    # Graphique 1 : Évolution Temporelle (Line Chart)
    with col_left:
        st.subheader("📅 Évolution dans le temps")
        if 'periode_label' in df.columns and 'sort_key' in df.columns:
            # Agrégation par période
            cols_to_agg = ['valeur_reelle']
            if 'valeur_objectif' in df.columns:
                cols_to_agg.append('valeur_objectif')
                
            df_time = df.groupby(['sort_key', 'periode_label'])[cols_to_agg].mean().reset_index()
            df_time = df_time.sort_values('sort_key')
            
            # Format long pour Plotly
            df_time_long = df_time.melt(id_vars=['periode_label', 'sort_key'], 
                                        var_name='Type', value_name='Score')
            
            # Mapping pour légende propre
            labels_map = {'valeur_reelle': 'Réel', 'valeur_objectif': 'Objectif'}
            df_time_long['Type'] = df_time_long['Type'].map(labels_map)
            
            fig_time = px.line(
                df_time_long, 
                x='periode_label', 
                y='Score', 
                color='Type',
                title="Évolution Moyenne",
                markers=True,
                color_discrete_map={'Réel': '#0055A4', 'Objectif': 'gray'}
            )
            fig_time.update_layout(xaxis_title="Période", yaxis_title="Score (%)")
            st.plotly_chart(fig_time, use_container_width=True)
        else:
            st.info("Données temporelles insuffisantes.")

    # Graphique 2 : Top/Flop Lignes (Bar Chart)
    with col_right:
        st.subheader("⚠️ Lignes à surveiller (Top 15 Flop)")
        if 'ligne' in df.columns and 'valeur_reelle' in df.columns:
            # Moyenne par ligne
            df_bar = df.groupby('ligne')['valeur_reelle'].mean().reset_index()
            # Tri pour avoir les pires en premier
            df_bar = df_bar.sort_values('valeur_reelle', ascending=True).head(15)
            
            fig_bar = px.bar(
                df_bar,
                x='valeur_reelle',
                y='ligne',
                orientation='h',
                title="Lignes avec les scores les plus bas",
                text_auto='.1f',
                color='valeur_reelle',
                color_continuous_scale='Redor'
            )
            fig_bar.update_layout(xaxis_title="Score (%)", yaxis_title="")
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("Information sur les lignes manquante.")

    # Graphique 3 : Par Thématique
    if 'thematique' in df.columns and 'valeur_reelle' in df.columns:
        st.subheader("🧩 Performance par Thématique")
        df_theme = df.groupby('thematique')['valeur_reelle'].mean().reset_index().sort_values('valeur_reelle')
        
        fig_theme = px.bar(
            df_theme,
            x='thematique',
            y='valeur_reelle',
            color='thematique',
            text_auto='.1f',
            title="Score moyen par catégorie de service"
        )
        # On ajuste l'échelle Y pour mieux voir les différences (souvent entre 80 et 100%)
        min_val = df_theme['valeur_reelle'].min()
        fig_theme.update_layout(yaxis_range=[max(0, min_val - 5), 105], showlegend=False)
        st.plotly_chart(fig_theme, use_container_width=True)

    # --- F. Données Brutes ---
    with st.expander("📋 Voir les données brutes filtrées"):
        st.dataframe(df)

    # --- G. Synthèse ---
    st.markdown("---")
    st.markdown("""
    ### 📝 Synthèse de l'analyse
    
    1.  **Tendances :** Le graphique temporel permet de valider si les plans d'actions portent leurs fruits trimestre après trimestre.
    2.  **Points chauds :** Le graphique des "Lignes à surveiller" met immédiatement en évidence les lignes nécessitant une intervention prioritaire.
    3.  **Thématiques :** L'analyse par thématique permet de savoir si la baisse de satisfaction vient de la régularité (souvent le cas) ou d'autres facteurs comme la propreté ou l'information.
    """)

if __name__ == "__main__":
    main()