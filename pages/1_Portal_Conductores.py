import streamlit as st
import pandas as pd
import urllib.parse
import urllib.request
import base64
import math
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
        return None

# --- 🔄 INICIALIZAR SESIÓN ---
if 'usuario_activo' not in st.session_state: st.session_state.usuario_activo = False
if 'datos_usuario' not in st.session_state: st.session_state.datos_usuario = {}

# --- 📋 LISTAS ---
PAISES = ["Ecuador", "Colombia", "Perú", "México", "España", "Otro"]
IDIOMAS = ["Español", "English"]
VEHICULOS = ["Taxi 🚖", "Camioneta 🛻", "Ejecutivo 🚔", "Moto Entrega 🏍️"]

# --- 🛰️ CAPTURA AUTOMÁTICA DE GPS ---
loc = get_geolocation()
lat_actual, lon_actual = (loc['coords']['latitude'], loc['coords']['longitude']) if loc and 'coords' in loc else (None, None)

# --- 📱 INTERFAZ ---
st.title("🚖 Portal de Socios")

if st.session_state.usuario_activo:
    df_fresh = cargar_datos("CHOFERES")
    user_nom = str(st.session_state.datos_usuario.get('Nombre', '')).strip()
    user_ape = str(st.session_state.datos_usuario.get('Apellido', '')).strip()
    nombre_completo_unificado = f"{user_nom} {user_ape}".upper()
    
    fila_actual = df_fresh[(df_fresh['Nombre'].astype(str).str.upper() == user_nom.upper()) & 
                           (df_fresh['Apellido'].astype(str).str.upper() == user_ape.upper())]
    
    if not fila_actual.empty:
        st.subheader(f"Bienvenido, {nombre_completo_unificado}")
        
        # --- RASTREO Y ESTADO ---
        if st.checkbox("🛰️ ACTIVAR RASTREO GPS", value=True):
            if lat_actual and lon_actual:
                enviar_datos({"accion": "actualizar_ubicacion", "conductor": nombre_completo_unificado, "latitud": lat_actual, "longitud": lon_actual})
                st.success(f"📍 Ubicación activa: {lat_actual}, {lon_actual}")

        st.metric("Tu Deuda Actual:", f"${float(fila_actual.iloc[0, 17]):.2f}")
        st.info(f"Estado Actual: **{fila_actual.iloc[0, 8]}**")

        # --- GESTIÓN DE VIAJE ---
        st.subheader("Gestión de Viaje")
        df_viajes = cargar_datos("VIAJES")
        viaje_activo = df_viajes[(df_viajes['Conductor Asignado'].astype(str).str.upper() == nombre_completo_unificado) & 
                                (df_viajes['Estado'].str.contains("EN CURSO"))] if not df_viajes.empty else pd.DataFrame()

        if not viaje_activo.empty:
            datos_v = viaje_activo.iloc[-1]
            st.warning("🚖 TIENES UN PASAJERO A BORDO")
            st.write(f"📍 **Destino:** {datos_v['Referencia']}")
            if st.button("🏁 FINALIZAR VIAJE Y COBRAR", type="primary", use_container_width=True):
                with st.spinner("Cobrando..."):
                    kms_finales = 1.0
                    if lat_actual and lon_actual:
                        try:
                            link_mapa = str(datos_v['Mapa'])
                            lat_c = float(link_mapa.split('query=')[1].split(',')[0])
                            lon_c = float(link_mapa.split('query=')[1].split(',')[1])
                            # Fórmula Haversine integrada para evitar NameError
                            dLat, dLon = math.radians(lat_actual - lat_c), math.radians(lon_actual - lon_c)
                            a = math.sin(dLat/2)**2 + math.cos(math.radians(lat_c)) * math.cos(math.radians(lat_actual)) * math.sin(dLon/2)**2
                            kms_finales = 2 * 6371 * math.asin(math.sqrt(a))
                        except: kms_finales = 5.0
                    
                    if enviar_datos({"accion": "terminar_via_je", "conductor": nombre_completo_unificado, "km": round(kms_finales, 2)}):
                        st.success("✅ Viaje finalizado.")
                        time.sleep(2)
                        st.rerun()

    if st.button("🔒 CERRAR SESIÓN"):
        st.session_state.usuario_activo = False
        st.rerun()
    st.stop()

else:
    tab_log, tab_reg = st.tabs(["🔐 INGRESAR", "📝 REGISTRARME"])
    with tab_log:
        l_nom, l_ape = st.text_input("Nombre"), st.text_input("Apellido")
        l_pass = st.text_input("Contraseña", type="password")
        if st.button("ENTRAR AL PANEL", type="primary"):
            df = cargar_datos("CHOFERES")
            match = df[(df['Nombre'].astype(str).str.upper() == l_nom.upper()) & 
                       (df['Apellido'].astype(str).str.upper() == l_ape.upper()) & 
                       (df['Clave'].astype(str) == l_pass)]
            if not match.empty:
                st.session_state.usuario_activo, st.session_state.datos_usuario = True, match.iloc[0].to_dict()
                st.rerun()

    with tab_reg:
        with st.form("registro_form"):
            st.subheader("Registro de Nuevos Socios")
            c1, c2 = st.columns(2)
            with c1:
                r_nom, r_ced, r_email = st.text_input("Nombres *"), st.text_input("Cédula *"), st.text_input("Email *")
                r_pais = st.selectbox("País", PAISES)
            with c2:
                r_ape, r_telf = st.text_input("Apellidos *"), st.text_input("WhatsApp *")
                r_veh = st.selectbox("Vehículo", VEHICULOS)
            r_dir, r_pla, r_pass1 = st.text_input("Dirección *"), st.text_input("Placa *"), st.text_input("Clave *", type="password")
            if st.form_submit_button("✅ COMPLETAR REGISTRO"):
                if r_nom and r_email and r_pass1:
                    res = enviar_datos({"accion": "registrar_conductor", "nombre": r_nom, "apellido": r_ape, "cedula": r_ced, "email": r_email, "direccion": r_dir, "telefono": r_telf, "placa": r_pla, "clave": r_pass1, "pais": r_pais, "Tipo_Vehiculo": r_veh})
                    if res: st.success("¡Registro exitoso!")

st.markdown('<div style="text-align:center; color:#888; font-size:12px; margin-top:50px;">© 2025 Taxi Seguro Global</div>', unsafe_allow_html=True)
