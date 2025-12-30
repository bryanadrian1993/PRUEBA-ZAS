import streamlit as st
import pandas as pd
import urllib.parse
import urllib.request
import base64
import math
import os
from datetime import datetime
from streamlit_js_eval import get_geolocation

# --- ⚙️ CONFIGURACIÓN DE NEGOCIO ---
TARIFA_POR_KM = 0.10        
DEUDA_MAXIMA = 10.00        
LINK_PAYPAL = "https://paypal.me/CAMPOVERDEJARAMILLO" 

# --- 🔗 CONFIGURACIÓN TÉCNICA ---
st.set_page_config(page_title="Portal Conductores", page_icon="🚖", layout="centered")
SHEET_ID = "1l3XXIoAggDd2K9PWnEw-7SDlONbtUvpYVw3UYD_9hus"
URL_SCRIPT = "https://script.google.com/macros/s/AKfycbwZowS5G8Xj1QFp7GngiP0DHVwu1f8v2bRIh-RPDmhYjlkLui2XF-40o0qv4GJd9Vvo/exec"

# --- 🔄 INICIALIZAR SESIÓN ---
if 'usuario_activo' not in st.session_state: st.session_state.usuario_activo = False
if 'datos_usuario' not in st.session_state: st.session_state.datos_usuario = {}

# --- 📋 LISTAS ---
PAISES = ["Ecuador", "Colombia", "Perú", "México", "España", "Otro"]
IDIOMAS = ["Español", "English"]
VEHICULOS = ["Taxi 🚖", "Camioneta 🛻", "Ejecutivo 🚔", "Moto Entrega 🏍️"]

# --- 🛠️ FUNCIONES ---
def cargar_datos(hoja):
    try:
        cache_buster = datetime.now().strftime("%Y%m%d%H%M%S")
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={hoja}&cb={cache_buster}"
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip() # Limpia espacios en nombres de columnas
        return df
    except: return pd.DataFrame()

def enviar_datos(datos):
    try:
        params = urllib.parse.urlencode(datos)
        url_final = f"{URL_SCRIPT}?{params}"
        with urllib.request.urlopen(url_final) as response:
            return response.read().decode('utf-8')
    except Exception as e: return f"Error: {e}"

# --- 📱 INTERFAZ ---
st.title("🚖 Portal de Socios")

if st.session_state.usuario_activo:
    # --- PANEL DEL CONDUCTOR LOGUEADO ---
    df_fresh = cargar_datos("CHOFERES")
    user_nom = str(st.session_state.datos_usuario['Nombre']).strip()
    user_ape = str(st.session_state.datos_usuario['Apellido']).strip()
    
    # Creamos el nombre completo EXACTO para sincronizar con la hoja UBICACIONES
    nombre_completo_unificado = f"{user_nom} {user_ape}".upper()
    
    # BUSCAMOS LA FILA DEL USUARIO EN EL EXCEL (Paso necesario para leer Deuda y Estado)
    fila_actual = df_fresh[
        (df_fresh['Nombre'].astype(str).str.upper().str.strip() == user_nom.upper()) & 
        (df_fresh['Apellido'].astype(str).str.upper().str.strip() == user_ape.upper())
    ]
    
    # --- LÓGICA DE ACTUALIZACIÓN DE UBICACIÓN ---
    st.subheader(f"Bienvenido, {nombre_completo_unificado}")
    
    if st.checkbox("🛰️ ACTIVAR RASTREO GPS"):
        try:
            # Asegúrate de tener lat_actual y lon_actual definidas arriba en tu código
            res = enviar_datos({
                "accion": "actualizar_ubicacion",
                "conductor": nombre_completo_unificado,
                "latitud": lat_actual,
                "longitud": lon_actual
            })
            if res:
                st.success("📍 Ubicación actualizada en tiempo real")
        except NameError:
            st.warning("Esperando señal de GPS...")
    
    # --- MOSTRAR INFORMACIÓN DEL SOCIO ---
    if not fila_actual.empty:
        # [cite_start]Columna R (Índice 17) es DEUDA [cite: 1]
        deuda_actual = float(fila_actual.iloc[0, 17])
        # [cite_start]Columna I (Índice 8) es Estado [cite: 1]
        estado_actual = str(fila_actual.iloc[0, 8]) 
        
        st.info(f"Estado Actual: **{estado_actual}**")
        st.metric("Tu Deuda Actual:", f"${deuda_actual:.2f}")
        st.success(f"✅ Socio: **{nombre_completo_unificado}**")
        
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("💸 Deuda Actual", f"${deuda_actual:.2f}")
        col_m2.metric("🚦 Estado Actual", estado_actual)

        # Botones de Acción
        st.subheader("Gestión de Disponibilidad")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🟢 PONERME LIBRE", use_container_width=True):
                enviar_datos({"accion": "actualizar_estado", "nombre": user_nom, "apellido": user_ape, "estado": "LIBRE"})
                st.rerun()
        with c2:
            if st.button("🔴 PONERME OCUPADO", use_container_width=True):
                enviar_datos({"accion": "actualizar_estado", "nombre": user_nom, "apellido": user_ape, "estado": "OCUPADO"})
                st.rerun()
        
        st.divider()
    
    if st.button("🔒 CERRAR SESIÓN"):
        st.session_state.usuario_activo = False
        st.rerun()

else:
    # --- PANTALLA INICIAL: LOGIN Y REGISTRO ---
    tab_log, tab_reg = st.tabs(["🔐 INGRESAR", "📝 REGISTRARME"])
    
    with tab_log:
        st.subheader("Acceso Socios")
        l_nom = st.text_input("Nombre registrado")
        l_ape = st.text_input("Apellido registrado")
        l_pass = st.text_input("Contraseña", type="password")
        
        if st.button("ENTRAR AL PANEL", type="primary"):
            df = cargar_datos("CHOFERES")
            # Validación por Nombre, Apellido y Clave
            match = df[(df['Nombre'].astype(str).str.upper() == l_nom.upper()) & 
                       (df['Apellido'].astype(str).str.upper() == l_ape.upper()) & 
                       (df['Clave'].astype(str) == l_pass)]
            
            if not match.empty:
                st.session_state.usuario_activo = True
                st.session_state.datos_usuario = match.iloc[0].to_dict()
                st.rerun()
            else:
                st.error("❌ Datos incorrectos o usuario no encontrado.")

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
            
            if st.form_submit_button("✅ COMPLETAR REGISTRO"):
                if r_nom and r_email and r_pass1:
                    res = enviar_datos({
                        "accion": "registrar_conductor", 
                        "nombre": r_nom, 
                        "apellido": r_ape, 
                        "cedula": r_ced, 
                        "email": r_email, 
                        "direccion": r_dir, 
                        "telefono": r_telf, 
                        "placa": r_pla, 
                        "clave": r_pass1, 
                        "pais": r_pais, 
                        "idioma": r_idioma, 
                        "Tipo_Vehiculo": r_veh
                    })
                    st.success("¡Registro exitoso! Ya puedes ingresar desde la pestaña superior.")
                else:
                    st.warning("Por favor, completa los campos obligatorios (*)")

st.markdown('<div style="text-align:center; color:#888; font-size:12px; margin-top:50px;">© 2025 Taxi Seguro Global</div>', unsafe_allow_html=True)
