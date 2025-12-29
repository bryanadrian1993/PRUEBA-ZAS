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

# --- ⚙️ CONFIGURACIÓN DE NEGOCIO ---
TARIFA_POR_KM = 0.05        
DEUDA_MAXIMA = 10.00        
LINK_PAYPAL = "https://paypal.me/CAMPOVERDEJARAMILLO" 
NUMERO_DEUNA = "09XXXXXXXX" 

# --- 🔗 CONFIGURACIÓN TÉCNICA ---
st.set_page_config(page_title="Portal Socios", page_icon="🚖", layout="centered")
SHEET_ID = "1l3XXIoAggDd2K9PWnEw-7SDlONbtUvpYVw3UYD_9hus"
# ✅ URL ACTUALIZADA Y VINCULADA
URL_SCRIPT = "https://script.google.com/macros/s/AKfycbwmdasUK1xYWaJjk-ytEAjepFazngTZ91qxhsuN0VZ0OgQmmjyZnD6nOnCNuwIL3HjD/exec"

if 'usuario_activo' not in st.session_state: st.session_state.usuario_activo = False
if 'datos_usuario' not in st.session_state: st.session_state.datos_usuario = {}
if 'ultima_lat' not in st.session_state: st.session_state.ultima_lat = None
if 'ultima_lon' not in st.session_state: st.session_state.ultima_lon = None

PAISES = ["Ecuador", "Colombia", "Perú", "México", "España", "Estados Unidos", "Argentina", "Brasil", "Chile", "Otro"]
VEHICULOS = ["Taxi 🚖", "Camioneta 🛻", "Ejecutivo 🚔", "Moto Entrega 🏍️"]

# --- 🛠️ FUNCIONES ---
def cargar_datos(hoja):
    try:
        cb = datetime.now().strftime("%Y%m%d%H%M%S")
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={hoja}&cb={cb}"
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        return df
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
    return 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)) * R

# --- 📱 INTERFAZ ---
st.title("🚖 Portal de Socios")

if st.session_state.usuario_activo:
    # --- PANEL DEL CONDUCTOR LOGUEADO ---
    df_fresh = cargar_datos("CHOFERES")
    user_nom = st.session_state.datos_usuario['Nombre']
    user_ape = st.session_state.datos_usuario['Apellido']
    fila_actual = df_fresh[(df_fresh['Nombre'].astype(str).str.upper() == str(user_nom).upper()) & 
                           (df_fresh['Apellido'].astype(str).str.upper() == str(user_ape).upper())]
    
    if not fila_actual.empty:
        deuda_actual = float(fila_actual.iloc[0, 17])
        bloqueado = deuda_actual >= DEUDA_MAXIMA

        st.success(f"✅ Socio: **{user_nom} {user_ape}**")

        if bloqueado:
            st.error(f"⛔ CUENTA BLOQUEADA POR DEUDA: ${deuda_actual:.2f}")
            if st.button("📱 MOSTRAR QR DEUNA"):
                st.info(f"Escanea el código o contacta al: {NUMERO_DEUNA}")
        else:
            st.metric("💸 Deuda Actual", f"${deuda_actual:.2f}")
            # Lógica de GPS/Estado aquí...
    
    if st.button("🔒 CERRAR SESIÓN"):
        st.session_state.usuario_activo = False
        st.rerun()

else:
    tab_log, tab_reg, tab_rec = st.tabs(["🔐 INGRESAR", "📝 REGISTRARME", "🔑 RECUPERAR"])
    
    with tab_log:
        l_nom = st.text_input("Nombre", key="l_n")
        l_ape = st.text_input("Apellido", key="l_a")
        l_pass = st.text_input("Contraseña", type="password", key="l_p")
        if st.button("ENTRAR AL PANEL"):
            df = cargar_datos("CHOFERES")
            match = df[(df['Nombre'].astype(str).str.upper() == l_nom.upper()) & 
                       (df['Apellido'].astype(str).str.upper() == l_ape.upper())]
            if not match.empty and str(match.iloc[0]['Clave']) == l_pass:
                st.session_state.usuario_activo = True
                st.session_state.datos_usuario = match.iloc[0].to_dict()
                st.rerun()
            else: st.error("Datos incorrectos")

    with tab_reg:
        with st.form("registro_form"):
            st.subheader("Registro de Nuevos Socios")
            r_nom = st.text_input("Nombres *")
            r_ape = st.text_input("Apellidos *")
            r_email = st.text_input("Email *")
            r_ced = st.text_input("Cédula/ID *")
            r_dir = st.text_input("Dirección *")
            r_pais = st.selectbox("País", PAISES)
            r_telf = st.text_input("WhatsApp *")
            r_veh = st.selectbox("Tipo de Vehículo", VEHICULOS)
            r_pla = st.text_input("Placa *")
            r_pass1 = st.text_input("Contraseña *", type="password")
            
            if st.form_submit_button("✅ COMPLETAR REGISTRO"):
                if r_nom and r_ape and r_email:
                    # ✅ Envío sincronizado con el script
                    res = enviar_datos({
                        "accion": "registrar_conductor", 
                        "nombre": r_nom, "apellido": r_ape, "email": r_email, 
                        "cedula": r_ced, "direccion": r_dir, "pais": r_pais,
                        "telefono": r_telf, "tipo_vehiculo": r_veh, 
                        "placa": r_pla, "clave": r_pass1
                    })
                    st.success("¡Registro exitoso! Ya puedes ingresar.")

    with tab_rec:
        st.subheader("¿Olvidaste tus datos?")
        rec_mail = st.text_input("Tu Email registrado")
        if st.button("✉️ ENVIAR CREDENCIALES"):
            res = enviar_datos({"accion": "recuperar_por_correo", "email": rec_mail})
            if res == "CORREO_ENVIADO": st.success("Revisa tu bandeja de entrada.")
            else: st.error("Email no encontrado.")

st.markdown('<div class="footer"><p>© 2025 Taxi Seguro Global<br>Contacto: taxi-seguro-world@hotmail.com</p></div>', unsafe_allow_html=True)
