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
import requests

# --- ⚙️ CONFIGURACIÓN DE NEGOCIO ---
TARIFA_POR_KM = 0.05
DEUDA_MAXIMA = 10.00
LINK_PAYPAL = "https://paypal.me/CAMPOVERDEJARAMILLO"

# --- 🔗 CONFIGURACIÓN TÉCNICA ---
st.set_page_config(page_title="Portal Conductores", page_icon="🚖", layout="centered")
SHEET_ID = "1l3XXIoAggDd2K9PWnEw-7SDlONbtUvpYVw3UYD_9hus"
URL_SCRIPT = "https://script.google.com/macros/s/AKfycbz-mcv2rnAiT10CUDxnnHA8sQ4XK0qLP7Hj2IhnzKp5xz5ugjP04HnQSN7OMvy4-4Al/exec"

def enviar_datos_requests(params):
    try:
        requests.post(URL_SCRIPT, params=params)
    except Exception as e:
        st.error(f"Error de conexión: {e}")

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

def enviar_datos_a_sheets(datos):
    try:
        params = urllib.parse.urlencode(datos)
        with urllib.request.urlopen(f"{URL_SCRIPT}?{params}") as response:
            return response.read().decode('utf-8')
    except: return "Error"

# --- 📱 INTERFAZ ---
st.title("🚖 Portal de Socios")

if st.session_state.usuario_activo:
    # --- PANEL DEL CONDUCTOR LOGUEADO ---
    df_fresh = cargar_datos("CHOFERES")
    user_nom = str(st.session_state.datos_usuario['Nombre']).strip()
    user_ape = str(st.session_state.datos_usuario['Apellido']).strip()
    nombre_completo_unificado = f"{user_nom} {user_ape}".upper()
    
    fila_actual = df_fresh[
        (df_fresh['Nombre'].astype(str).str.upper().str.strip() == user_nom.upper()) & 
        (df_fresh['Apellido'].astype(str).str.upper().str.strip() == user_ape.upper())
    ]
    
    st.subheader(f"Bienvenido, {nombre_completo_unificado}")

    # --- FOTO DE PERFIL ---
    foto_actual = st.session_state.datos_usuario.get('Foto_Perfil', 'SIN_FOTO')
    if foto_actual == "SIN_FOTO" and not fila_actual.empty:
        try: foto_actual = fila_actual.iloc[0]['Foto_Perfil']
        except: pass

    col_img, col_btn = st.columns([1, 2])
    with col_img:
        if foto_actual and str(foto_actual) != "nan" and len(str(foto_actual)) > 100:
            try:
                img_bytes = base64.b64decode(foto_actual)
                st.image(io.BytesIO(img_bytes), width=150)
            except: st.image("https://cdn-icons-png.flaticon.com/512/149/149071.png", width=120)
        else: st.image("https://cdn-icons-png.flaticon.com/512/149/149071.png", width=120)

    with col_btn:
        st.write("📷 **¿Cambiar foto?**")
        archivo_nuevo = st.file_uploader("Sube imagen (150x150)", type=["jpg", "png"], key="p_foto")
        if archivo_nuevo and st.button("💾 GUARDAR FOTO"):
            with st.spinner("Guardando..."):
                img = Image.open(archivo_nuevo).convert("RGB").resize((150, 150))
                buffered = io.BytesIO()
                img.save(buffered, format="JPEG", quality=60)
                foto_b64 = base64.b64encode(buffered.getvalue()).decode()
                res = enviar_datos({"accion": "actualizar_foto_perfil", "email": fila_actual.iloc[0]['Email'], "foto": foto_b64})
                if res:
                    st.session_state.datos_usuario['Foto_Perfil'] = foto_b64
                    st.success("✅ Foto guardada")
                    time.sleep(1)
                    st.rerun()

    st.write("---")
    if st.checkbox("🛰️ ACTIVAR RASTREO GPS", value=True):
        if lat_actual and lon_actual:
            res = enviar_datos({"accion": "actualizar_ubicacion", "conductor": nombre_completo_unificado, "latitud": lat_actual, "longitud": lon_actual})
            if res: st.success(f"📍 Ubicación activa: {lat_actual}, {lon_actual}")
        else: st.warning("Esperando señal GPS...")

    # --- MOSTRAR INFORMACIÓN DEL SOCIO ---
    if not fila_actual.empty:
        deuda_actual = float(fila_actual.iloc[0, 17])
        estado_actual = str(fila_actual.iloc[0, 8])
        
        # Bloqueo Automático
        if deuda_actual >= DEUDA_MAXIMA and "LIBRE" in estado_actual.upper():
            st.error("⚠️ DESCONEXIÓN AUTOMÁTICA: Tu deuda superó el límite permitido.")
            enviar_datos({"accion": "actualizar_estado", "nombre": user_nom, "apellido": user_ape, "estado": "OCUPADO"})
            time.sleep(1)
            st.rerun()

        # -------------------------------------------------------------
        # ✅ AQUI ESTÁ LA SECCIÓN DE PAGOS (Antes no estaba)
        # -------------------------------------------------------------
        
        # 1. Métricas visuales
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("💸 Deuda Actual", f"${deuda_actual:.2f}")
        col_m2.metric("🚦 Estado Actual", estado_actual)

        # 2. SECCIÓN DE PAGOS (Solo aparece si la deuda es mayor a 0)
        if deuda_actual > 0:
            st.markdown("---")
            st.subheader("💳 Centro de Pagos")
            st.warning(f"Saldo pendiente: **${deuda_actual:.2f}**")
            
            tab_deuna, tab_paypal = st.tabs(["📲 Pagar con DEUNA", "🌎 Pagar con PAYPAL"])
            
            with tab_deuna:
                st.write("**Escanea el QR:**")
                try: 
                    # Intenta cargar qr_deuna.png
                    st.image("qr_deuna.png", caption="QR Banco Pichincha", width=250)
                except: 
                    st.error("⚠️ Sube 'qr_deuna.png' a GitHub")
                st.info("Envía el comprobante al admin.")

            with tab_paypal:
                st.write("**Pagar con saldo/tarjeta:**")
                st.markdown(f'''<a href="{LINK_PAYPAL}" target="_blank" style="text-decoration:none;"><div style="background-color:#0070ba;color:white;padding:12px;text-align:center;border-radius:10px;font-weight:bold;">🔵 IR A PAYPAL</div></a>''', unsafe_allow_html=True)
            st.divider()
        # -------------------------------------------------------------

        # --- GESTIÓN DE VIAJE ---
        st.subheader("Gestión de Viaje")
        df_viajes = cargar_datos("VIAJES")
        viaje_activo = pd.DataFrame()
        if not df_viajes.empty and 'Conductor' in df_viajes.columns:
            viaje_activo = df_viajes[
                (df_viajes['Conductor'].astype(str).str.upper() == nombre_completo_unificado) & 
                (df_viajes['Estado'].astype(str) == "EN CURSO")
            ]

        if not viaje_activo.empty and "OCUPADO" in estado_actual:
            datos_v = viaje_activo.iloc[-1]
            st.warning("🚖 TIENES UN PASAJERO A BORDO")
            st.write(f"👤 **Cliente:** {datos_v.get('Cliente', 'S/D')}")
            st.write(f"📞 **Tel:** {datos_v.get('Tel Cliente', 'S/D')}")
            st.write(f"📍 **Destino:** {datos_v.get('Referencia', 'S/D')}")
            st.markdown(f"[🗺️ Ver Mapa]({datos_v.get('Mapa', '#')})")

            if st.button("🏁 FINALIZAR VIAJE Y COBRAR", type="primary", use_container_width=True):
                with st.spinner("Procesando..."):
                    try:
                        link_mapa = str(datos_v.get('Mapa', ''))
                        distancia = 2.0 
                        if '0' in link_mapa and ',' in link_mapa:
                            try:
                                lat_cli = float(link_mapa.split('0')[1].split(',')[0])
                                lon_cli = float(link_mapa.split('0')[1].split(',')[1])
                                dLat = math.radians(lat_actual - lat_cli)
                                dLon = math.radians(lon_actual - lon_cli)
                                a = math.sin(dLat/2)**2 + math.cos(math.radians(lat_cli)) * math.cos(math.radians(lat_actual)) * math.sin(dLon/2)**2
                                c = 2 * math.asin(math.sqrt(a))
                                distancia = 6371 * c
                            except: pass
                        if distancia < 1.0: distancia = 1.0
                        comision = round(distancia * TARIFA_POR_KM, 2)
                        
                        res = enviar_datos_a_sheets({
                            "accion": "finalizar_y_deuda",
                            "conductor": nombre_completo_unificado,
                            "comision": comision,
                            "km": round(distancia, 2)
                        })
                        if res == "Ok":
                            st.balloons()
                            st.success(f"✅ Finalizado. Comisión: ${comision}")
                            time.sleep(2)
                            st.rerun()
                        else: st.error("Error de conexión.")
                    except Exception as e: st.error(f"Error: {e}")

        else:
            if deuda_actual >= 10.00:
                st.error(f"🚫 CUENTA BLOQUEADA POR DEUDA (${deuda_actual:.2f})")
                st.info("⬆️ Usa las opciones de arriba para pagar y desbloquearte.")
                st.button("🟢 PONERME LIBRE", disabled=True)
            else:
                col_lib, col_ocu = st.columns(2)
                with col_lib:
                    if st.button("🟢 PONERME LIBRE", use_container_width=True):
                        enviar_datos({"accion": "actualizar_estado", "nombre": user_nom, "apellido": user_ape, "estado": "LIBRE"})
                        st.rerun()
                with col_ocu:
                    if st.button("🔴 PONERME OCUPADO", use_container_width=True):
                        enviar_datos({"accion": "actualizar_estado", "nombre": user_nom, "apellido": user_ape, "estado": "OCUPADO"})
                        st.rerun()

    with st.expander("📜 Ver Historial"):
        if 'df_viajes' not in locals(): df_viajes = cargar_datos("VIAJES")
        if not df_viajes.empty and 'Conductor Asignado' in df_viajes.columns:
            mis_viajes = df_viajes[df_viajes['Conductor Asignado'].astype(str).str.upper() == nombre_completo_unificado]
            st.dataframe(mis_viajes[['Fecha', 'Referencia', 'Estado']], use_container_width=True)

    if st.button("🔒 CERRAR SESIÓN"):
        st.session_state.usuario_activo = False
        st.rerun()
    st.stop()

else:
    # --- LOGIN ---
    tab_log, tab_reg = st.tabs(["🔐 INGRESAR", "📝 REGISTRARME"])
    with tab_log:
        st.subheader("Acceso Socios")
        l_nom = st.text_input("Nombre registrado")
        l_ape = st.text_input("Apellido registrado")
        l_pass = st.text_input("Contraseña", type="password")
        if st.button("ENTRAR AL PANEL", type="primary"):
            df = cargar_datos("CHOFERES")
            match = df[(df['Nombre'].astype(str).str.upper() == l_nom.upper()) & (df['Apellido'].astype(str).str.upper() == l_ape.upper()) & (df['Clave'].astype(str) == l_pass)]
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
                r_telf = st.text_input("WhatsApp *")
                r_veh = st.selectbox("Vehículo *", VEHICULOS)
                r_idioma = st.selectbox("Idioma", IDIOMAS)
            r_dir = st.text_input("Dirección *")
            r_pla = st.text_input("Placa *")
            r_pass1 = st.text_input("Contraseña *", type="password")
            st.write("---")
            st.write("📷 **Foto de Perfil**")
            archivo_foto_reg = st.file_uploader("Sube tu foto", type=["jpg", "png", "jpeg"])
            
            if st.form_submit_button("✅ COMPLETAR REGISTRO"):
                if r_nom and r_email and r_pass1:
                    foto_b64 = "SIN_FOTO"
                    if archivo_foto_reg:
                        try:
                            img = Image.open(archivo_foto_reg).resize((150, 150))
                            buf = io.BytesIO()
                            img.save(buf, format="JPEG")
                            foto_b64 = base64.b64encode(buf.getvalue()).decode()
                        except: pass
                    res = enviar_datos({"accion": "registrar_conductor", "nombre": r_nom, "apellido": r_ape, "cedula": r_ced, "email": r_email, "direccion": r_dir, "telefono": r_telf, "placa": r_pla, "clave": r_pass1, "foto": foto_b64, "pais": r_pais, "idioma": r_idioma, "Tipo_Vehiculo": r_veh})
                    if res: st.success("¡Registro exitoso! Ingresa arriba.")
                else: st.warning("Completa los campos obligatorios (*)")
    
    st.markdown("---")
    with st.expander("¿Olvidaste tu contraseña?"):
        email_recup = st.text_input("Tu Email", key="email_recup")
        if st.button("📧 Recuperar Clave"):
            requests.post(URL_SCRIPT, params={"accion": "recuperar_clave", "email": email_recup})
            st.success("Si el correo existe, recibirás tu clave pronto.")

st.markdown('<div style="text-align:center; color:#888; font-size:12px; margin-top:50px;">© 2025 Taxi Seguro Global</div>', unsafe_allow_html=True)

import time
if st.session_state.get('usuario_activo', False):
    datos = st.session_state.get('datos_usuario', {})
    if "LIBRE" in str(datos.get('estado', 'OCUPADO')):
        time.sleep(15)
        st.rerun()
