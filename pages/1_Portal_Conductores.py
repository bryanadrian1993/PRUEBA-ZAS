import streamlit as st
import pandas as pd
import urllib.parse
import urllib.request
import base64
import math
import os
import re
from datetime import datetime
from streamlit_js_eval import get_geolocation

# --- 🔗 CONFIGURACIÓN TÉCNICA ---
st.set_page_config(page_title="Portal Conductores", page_icon="🚖", layout="centered")
SHEET_ID = "1l3XXIoAggDd2K9PWnEw-7SDlONbtUvpYVw3UYD_9hus"
URL_SCRIPT = "https://script.google.com/macros/s/AKfycbzivwxOGYSA33ekluigM6o6ZwwmavUKnzmEMxBUftKYqbblGGvbbYomci2qJE8zuYZi/exec"

# --- 🔄 INICIALIZAR SESIÓN ---
if 'usuario_activo' not in st.session_state: st.session_state.usuario_activo = False
if 'datos_usuario' not in st.session_state: st.session_state.datos_usuario = {}

# --- 🛠️ FUNCIONES ---
def cargar_datos(hoja):
    try:
        cb = datetime.now().strftime("%Y%m%d%H%M%S")
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={hoja}&cb={cb}"
        return pd.read_csv(url)
    except: return pd.DataFrame()

def enviar_datos(datos):
    try:
        params = urllib.parse.urlencode(datos)
        with urllib.request.urlopen(f"{URL_SCRIPT}?{params}") as response:
            return response.read().decode('utf-8')
    except: return "Error"

def calcular_distancia(lat1, lon1, lat2, lon2):
    R = 6371 
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    # ✅ CORRECCIÓN DE SINTAXIS AQUÍ
    return 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)) * R

# --- 📱 INTERFAZ ---
st.title("🚖 Portal de Socios")

if st.session_state.usuario_activo:
    st.success(f"✅ Socio: **{st.session_state.datos_usuario['Nombre']}**")
    if st.button("🔒 CERRAR SESIÓN"):
        st.session_state.usuario_activo = False
        st.rerun()
else:
    # --- PANTALLA INICIAL: LOGIN, REGISTRO Y RECUPERACIÓN ---
    tab_log, tab_reg, tab_rec = st.tabs(["🔐 INGRESAR", "📝 REGISTRARME", "🔑 RECUPERAR"])
    
    with tab_log:
        l_nom = st.text_input("Nombre", key="l_n")
        l_ape = st.text_input("Apellido", key="l_a")
        l_pass = st.text_input("Contraseña", type="password", key="l_p")
        if st.button("ENTRAR AL PANEL", type="primary"):
            df = cargar_datos("CHOFERES")
            match = df[(df['Nombre'].astype(str).str.upper() == l_nom.upper()) & (df['Apellido'].astype(str).str.upper() == l_ape.upper())]
            if not match.empty and str(match.iloc[0]['Clave']) == l_pass:
                st.session_state.usuario_activo = True
                st.session_state.datos_usuario = match.iloc[0].to_dict()
                st.rerun()
            else: st.error("Datos incorrectos")

    with tab_reg:
        with st.form("registro_form"):
            r_nom = st.text_input("Nombres *")
            r_ape = st.text_input("Apellidos *")
            r_email = st.text_input("Email *")
            r_pass = st.text_input("Contraseña *", type="password")
            if st.form_submit_button("✅ REGISTRAR"):
                enviar_datos({"accion": "registrar_conductor", "nombre": r_nom, "apellido": r_ape, "email": r_email, "clave": r_pass})
                st.success("¡Registrado!")

    with tab_rec:
        st.subheader("¿Olvidaste tus datos?")
        st.info("Ingresa tu correo electrónico registrado para recibir tu usuario y contraseña.")
        rec_email = st.text_input("Tu Correo Electrónico", key="email_rec")
        if st.button("✉️ ENVIAR CREDENCIALES AL CORREO"):
            if rec_email:
                with st.spinner("Buscando..."):
                    res = enviar_datos({"accion": "recuperar_por_correo", "email": rec_email})
                    if res == "CORREO_ENVIADO":
                        st.success(f"✅ ¡Enviado! Revisa tu bandeja de entrada: {rec_email}")
                        st.balloons()
                    elif res == "EMAIL_NO_ENCONTRADO":
                        st.error("❌ No existe una cuenta con ese correo.")
                    else:
                        st.error("Hubo un error al enviar el correo.")
            else:
                st.warning("Escribe tu correo primero.")

st.markdown('<div style="text-align:center; color:#888; font-size:12px; margin-top:50px;">© 2025 Taxi Seguro Global</div>', unsafe_allow_html=True)
