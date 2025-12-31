import streamlit as st
import pandas as pd
import urllib.parse
import urllib.request
import base64
from math import radians, cos, sin, asin, sqrt
import os
import time
import io
from PIL import Image
from datetime import datetime
from streamlit_js_eval import get_geolocation

# --- ⚙️ CONFIGURACIÓN DE NEGOCIO ---
TARIFA_POR_KM = 0.05        
DEUDA_MAXIMA = 10.00        
LINK_PAYPAL = "https://paypal.me/CAMPOVERDEJARAMILLO" 

# --- 🔗 CONFIGURACIÓN TÉCNICA ---
st.set_page_config(page_title="Portal Conductores", page_icon="🚖", layout="centered")
SHEET_ID = "1l3XXIoAggDd2K9PWnEw-7SDlONbtUvpYVw3UYD_9hus"
URL_SCRIPT = "https://script.google.com/macros/s/AKfycbxvsj1h8xSsbyIlo7enfZWO2Oe1IVJer3KHpUO_o08gkRGJKmFnH0wNRvQRa38WWKgv/exec"
import requests 

# --- 💾 FUNCIÓN DE PERSISTENCIA ---
from streamlit_javascript import st_javascript
import json

def gestionar_autologin():
    user_data = st_javascript("localStorage.getItem('user_taxi_seguro');")
    if user_data and user_data != "null":
        try:
            return json.loads(user_data)
        except:
            return None
    return None

def enviar_datos_post(params):
    try:
        requests.post(URL_SCRIPT, params=params)
    except Exception as e:
        st.error(f"Error de conexión: {e}")

# --- 🔄 INICIALIZAR SESIÓN CON AUTO-LOGIN ---
if 'usuario_activo' not in st.session_state:
    datos_recuperados = gestionar_autologin()
    if datos_recuperados:
        st.session_state.usuario_activo = True
        st.session_state.datos_usuario = datos_recuperados
    else:
        st.session_state.usuario_activo = False

if 'datos_usuario' not in st.session_state:
    st.session_state.datos_usuario = {}

# --- 📋 LISTAS ---
PAISES = ["Ecuador", "Colombia", "Perú", "México", "España", "Otro"]
IDIOMAS = ["Español", "English"]
VEHICULOS = ["Taxi 🚖", "Camioneta 🛻", "Ejecutivo 🚔", "Moto Entrega 🏍️"]

# --- 🛰️ CAPTURA AUTOMÁTICA DE GPS ---
loc = get_geolocation()
if loc and 'coords' in loc:
    lat_actual = loc['coords']['latitude']
    lon_actual = loc['coords']['longitude']
else:
    lat_actual, lon_actual = None, None

# --- 🛠️ FUNCIONES ---
def cargar_datos(hoja):
    gid = "773119638" if hoja == "CHOFERES" else "0"
    try:
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        return df
    except:
        return pd.DataFrame()

def enviar_datos(datos):
    try:
        params = urllib.parse.urlencode(datos)
        url_final = f"{URL_SCRIPT}?{params}"
        with urllib.request.urlopen(url_final) as response:
            return response.read().decode('utf-8')
    except: 
        return f"Error"

# --- 📱 INTERFAZ ---
st.title("🚖 Portal de Socios")

if st.session_state.usuario_activo:
    df_fresh = cargar_datos("CHOFERES")
    user_nom = str(st.session_state.datos_usuario.get('Nombre', '')).strip()
    user_ape = str(st.session_state.datos_usuario.get('Apellido', '')).strip()
    nombre_completo_unificado = f"{user_nom} {user_ape}".upper()
    
    fila_actual = df_fresh[
        (df_fresh['Nombre'].astype(str).str.upper().str.strip() == user_nom.upper()) & 
        (df_fresh['Apellido'].astype(str).str.upper().str.strip() == user_ape.upper())
    ]
    
    if not fila_actual.empty:
        st.subheader(f"Bienvenido, {nombre_completo_unificado}")
        
        # --- SECCIÓN DE RASTREO Y MÉTRICAS ---
        if st.checkbox("🛰️ ACTIVAR RASTREO GPS", value=True):
            if lat_actual and lon_actual:
                enviar_datos({"accion": "actualizar_ubicacion", "conductor": nombre_completo_unificado, "latitud": lat_actual, "longitud": lon_actual})
                st.success(f"📍 Ubicación activa: {lat_actual}, {lon_actual}")
        
        deuda_val = float(fila_actual.iloc[0, 17])
        st.metric("Tu Deuda Actual:", f"${deuda_val:.2f}")
        st.info(f"Estado Actual: **{fila_actual.iloc[0, 8]}**")

        st.subheader("Gestión de Viaje")
        df_viajes = cargar_datos("VIAJES")
        if not df_viajes.empty:
            viaje_activo = df_viajes[
                (df_viajes['Conductor Asignado'].astype(str).str.upper() == nombre_completo_unificado) & 
                (df_viajes['Estado'].str.contains("EN CURSO"))
            ]
            
            if not viaje_activo.empty:
                datos_v = viaje_activo.iloc[-1]
                st.warning("🚖 TIENES UN PASAJERO A BORDO")
                st.write(f"📍 **Destino:** {datos_v['Referencia']}")
                st.markdown(f"[🗺️ Ver Mapa]({datos_v['Mapa']})")

                if st.button("🏁 FINALIZAR VIAJE Y COBRAR", type="primary", use_container_width=True):
                    with st.spinner("Calculando cobro..."):
                        kms_finales = 1.0
                        if lat_actual and lon_actual:
                            try:
                                link_mapa = str(datos_v['Mapa'])
                                lat_c = float(link_mapa.split('query=')[1].split(',')[0])
                                lon_c = float(link_mapa.split('query=')[1].split(',')[1])
                                url_osrm = f"http://router.project-osrm.org/route/v1/driving/{lon_c},{lat_c};{lon_actual},{lat_actual}?overview=false"
                                kms_finales = requests.get(url_osrm).json()['routes'][0]['distance'] / 1000
                            except:
                                # BLOQUE DE RESPALDO CORREGIDO
                                dLat = radians(lat_actual - lat_c)
                                dLon = radians(lon_actual - lon_c)
                                a = sin(dLat/2)**2 + cos(radians(lat_c)) * cos(radians(lat_actual)) * sin(dLon/2)**2
                                kms_finales = 2 * 6371 * asin(sqrt(a))

                        if enviar_datos({"accion": "terminar_viaje", "conductor": nombre_completo_unificado, "km": round(kms_finales, 2)}):
                            st.success("✅ Viaje finalizado.")
                            time.sleep(2)
                            st.rerun()

    if st.button("🔒 CERRAR SESIÓN"):
        st_javascript("localStorage.removeItem('user_taxi_seguro');")
        st.session_state.usuario_activo = False
        st.rerun()

else:
    tab_log, tab_reg = st.tabs(["🔐 INGRESAR", "📝 REGISTRARME"])
    with tab_log:
        st.subheader("Acceso Socios")
        l_nom = st.text_input("Nombre")
        l_ape = st.text_input("Apellido")
        l_pass = st.text_input("Contraseña", type="password")
        if st.button("ENTRAR AL PANEL", type="primary"):
            df = cargar_datos("CHOFERES")
            match = df[(df['Nombre'].astype(str).str.upper() == l_nom.upper()) & (df['Apellido'].astype(str).str.upper() == l_ape.upper()) & (df['Clave'].astype(str) == l_pass)]
            if not match.empty:
                st.session_state.usuario_activo, st.session_state.datos_usuario = True, match.iloc[0].to_dict()
                st_javascript(f"localStorage.setItem('user_taxi_seguro', '{json.dumps(st.session_state.datos_usuario)}');")
                st.rerun()
    with tab_reg:
        with st.form("registro_form"):
            st.subheader("Registro de Nuevos Socios")
            r_nom = st.text_input("Nombres *")
            r_email = st.text_input("Email *")
            if st.form_submit_button("✅ COMPLETAR REGISTRO"):
                st.info("Función de registro activa.")
