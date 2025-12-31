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
    GID_CHOFERES = "773119638"
    GID_VIAJES   = "0"
    try:
        gid_actual = GID_CHOFERES if hoja == "CHOFERES" else GID_VIAJES
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid_actual}"
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        return pd.DataFrame()

def enviar_datos(datos):
    try:
        params = urllib.parse.urlencode(datos)
        url_final = f"{URL_SCRIPT}?{params}"
        with urllib.request.urlopen(url_final) as response:
            return response.read().decode('utf-8')
    except Exception as e: return f"Error: {e}"

# --- 🔄 INICIALIZAR SESIÓN ---
if 'usuario_activo' not in st.session_state: st.session_state.usuario_activo = False
if 'datos_usuario' not in st.session_state: st.session_state.datos_usuario = {}

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

# --- 📱 INTERFAZ ---
st.title("🚖 Portal de Socios")

if st.session_state.usuario_activo:
    # (Panel del Conductor - Se mantiene igual)
    df_fresh = cargar_datos("CHOFERES")
    user_nom = str(st.session_state.datos_usuario.get('Nombre', '')).strip()
    user_ape = str(st.session_state.datos_usuario.get('Apellido', '')).strip()
    nombre_completo_unificado = f"{user_nom} {user_ape}".upper()
    
    fila_actual = df_fresh[
        (df_fresh['Nombre'].astype(str).str.upper().str.strip() == user_nom.upper()) & 
        (df_fresh['Apellido'].astype(str).str.upper().str.strip() == user_ape.upper())
    ]
    
    st.subheader(f"Bienvenido, {nombre_completo_unificado}")

    # --- GESTIÓN DE VIAJE Y BOTÓN DE COBRO CORREGIDO ---
    st.subheader("Gestión de Viaje")
    df_viajes = cargar_datos("VIAJES")
    if not df_viajes.empty and 'Conductor Asignado' in df_viajes.columns:
        viaje_activo = df_viajes[
            (df_viajes['Conductor Asignado'].astype(str).str.upper() == nombre_completo_unificado) & 
            (df_viajes['Estado'].astype(str).str.contains("EN CURSO"))
        ]

        if not viaje_activo.empty:
            datos_v = viaje_activo.iloc[-1]
            st.warning("🚖 TIENES UN PASAJERO A BORDO")
            if st.button("🏁 FINALIZAR VIAJE Y COBRAR", type="primary", use_container_width=True):
                with st.spinner("Calculando..."):
                    kms_finales = 1.0
                    if lat_actual and lon_actual:
                        try:
                            link_mapa = str(datos_v['Mapa'])
                            lat_c = float(link_mapa.split('query=')[1].split(',')[0])
                            lon_c = float(link_mapa.split('query=')[1].split(',')[1])
                            # Fórmula Haversine integrada
                            dLat = math.radians(lat_actual - lat_c)
                            dLon = math.radians(lon_actual - lon_c)
                            a = math.sin(dLat/2)**2 + math.cos(math.radians(lat_c)) * math.cos(math.radians(lat_actual)) * math.sin(dLon/2)**2
                            kms_finales = 2 * 6371 * math.asin(math.sqrt(a))
                            if kms_finales < 0.5: kms_finales = 1.0
                        except: kms_finales = 5.0
                    
                    res = enviar_datos({"accion": "terminar_viaje", "conductor": nombre_completo_unificado, "km": round(kms_finales, 2)})
                    if res:
                        st.success(f"✅ Finalizado: {kms_finales:.2f} km.")
                        time.sleep(2)
                        st.rerun()

    if st.button("🔒 CERRAR SESIÓN"):
        st.session_state.usuario_activo = False
        st.rerun()
    st.stop()

else:
    tab_log, tab_reg = st.tabs(["🔐 INGRESAR", "📝 REGISTRARME"])

    with tab_log:
        st.subheader("Acceso Socios")
        l_nom = st.text_input("Nombre registrado")
        l_ape = st.text_input("Apellido registrado")
        l_pass = st.text_input("Contraseña", type="password")
        if st.button("ENTRAR AL PANEL", type="primary"):
            df = cargar_datos("CHOFERES")
            match = df[(df['Nombre'].astype(str).str.upper() == l_nom.upper()) & 
                       (df['Apellido'].astype(str).str.upper() == l_ape.upper()) & 
                       (df['Clave'].astype(str) == l_pass)]
            if not match.empty:
                st.session_state.usuario_activo = True
                st.session_state.datos_usuario = match.iloc[0].to_dict()
                st.rerun()
            else: st.error("❌ Datos incorrectos.")

    with tab_reg:
        with st.form("registro_form"):
            st.subheader("Registro de Nuevos Socios")
            col1, col2 = st.columns(2)
            with col1:
                r_nom = st.text_input("Nombres *")
                r_ced = st.text_input("Cédula/ID *")
                r_email = st.text_input("Email *")
                r_pais = st.selectbox("País *", PAISES)
            with col2:
                r_ape = st.text_input("Apellidos *")
                r_telf = st.text_input("WhatsApp (Sin código) *")
                r_veh = st.selectbox("Tipo de Vehículo *", VEHICULOS)
                r_idioma = st.selectbox("Idioma", IDIOMAS)
            
            r_dir = st.text_input("Dirección *")
            r_pla = st.text_input("Placa *")
            r_pass1 = st.text_input("Contraseña *", type="password")
            
            st.write("📷 **Foto de Perfil** (Opcional)")
            archivo_foto_reg = st.file_uploader("Sube tu foto", type=["jpg", "png", "jpeg"])
            
            if st.form_submit_button("✅ COMPLETAR REGISTRO"):
                if r_nom and r_email and r_pass1:
                    foto_para_guardar = "SIN_FOTO"
                    if archivo_foto_reg:
                        img = Image.open(archivo_foto_reg).convert("RGB").resize((150, 150))
                        buffered = io.BytesIO()
                        img.save(buffered, format="JPEG", quality=70)
                        foto_para_guardar = base64.b64encode(buffered.getvalue()).decode()
                    
                    res = enviar_datos({
                        "accion": "registrar_conductor", "nombre": r_nom, "apellido": r_ape, 
                        "cedula": r_ced, "email": r_email, "direccion": r_dir, 
                        "telefono": r_telf, "placa": r_pla, "clave": r_pass1, 
                        "foto": foto_para_guardar, "pais": r_pais, "idioma": r_idioma, "Tipo_Vehiculo": r_veh
                    })
                    if res: st.success("¡Registro exitoso! Ya puedes ingresar.")
                else: st.warning("Completa los campos obligatorios (*)")

st.markdown('<div style="text-align:center; color:#888; font-size:12px; margin-top:50px;">© 2025 Taxi Seguro Global</div>', unsafe_allow_html=True)
