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
NUMERO_DEUNA = "09XXXXXXXX" # Pon tu número de Deuna aquí

# --- 🔗 CONFIGURACIÓN TÉCNICA ---
st.set_page_config(page_title="Portal Conductores", page_icon="🚖", layout="centered")
SHEET_ID = "1l3XXIoAggDd2K9PWnEw-7SDlONbtUvpYVw3UYD_9hus"
URL_SCRIPT = "https://script.google.com/macros/s/AKfycbwzOVH8c8f9WEoE4OJOTIccz_EgrOpZ8ySURTVRwi0bnQhFnWVdgfX1W8ivTIu5dFfs/exec"

# --- 🔄 INICIALIZAR SESIÓN ---
if 'usuario_activo' not in st.session_state: st.session_state.usuario_activo = False
if 'datos_usuario' not in st.session_state: st.session_state.datos_usuario = {}
if 'ultima_lat' not in st.session_state: st.session_state.ultima_lat = None
if 'ultima_lon' not in st.session_state: st.session_state.ultima_lon = None

# --- 📋 LISTAS ---
PAISES = ["Ecuador", "Colombia", "Perú", "México", "España", "Estados Unidos", "Argentina", "Brasil", "Chile", "Otro"]
IDIOMAS = ["Español", "English", "Português", "Français", "Italiano", "Deutsch", "Otro"]
VEHICULOS = ["Taxi 🚖", "Camioneta 🛻", "Ejecutivo 🚔", "Moto Entrega 🏍️"]

# --- 🛠️ FUNCIONES ---
def cargar_datos(hoja):
    try:
        cache_buster = datetime.now().strftime("%Y%m%d%H%M%S")
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={hoja}&cb={cache_buster}"
        return pd.read_csv(url)
    except: return pd.DataFrame()

def enviar_datos(datos):
    try:
        params = urllib.parse.urlencode(datos)
        url_final = f"{URL_SCRIPT}?{params}"
        with urllib.request.urlopen(url_final) as response:
            return response.read().decode('utf-8')
    except Exception as e: return f"Error: {e}"

def calcular_distancia(lat1, lon1, lat2, lon2):
    R = 6371 
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)) * R

# --- 📱 INTERFAZ ---
st.title("🚖 Portal de Socios")

if st.session_state.usuario_activo:
    # --- PANEL DEL CONDUCTOR LOGUEADO ---
    df_fresh = cargar_datos("CHOFERES")
    user_nom = st.session_state.datos_usuario['Nombre']
    user_ape = st.session_state.datos_usuario['Apellido']
    fila_actual = df_fresh[(df_fresh['Nombre'] == user_nom) & (df_fresh['Apellido'] == user_ape)]
    
    # Referencia por posición de columna para evitar KeyErrors
    km_actuales = float(fila_actual.iloc[0, 16]) if not fila_actual.empty else 0.0
    deuda_actual = float(fila_actual.iloc[0, 17]) if not fila_actual.empty else 0.0
    bloqueado = deuda_actual >= DEUDA_MAXIMA

    st.success(f"✅ Socio: **{user_nom} {user_ape}**")

    if bloqueado:
        st.error(f"⛔ CUENTA BLOQUEADA POR DEUDA: ${deuda_actual:.2f}")
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            st.markdown(f'''<a href="{LINK_PAYPAL}" target="_blank" style="text-decoration:none;"><div style="background-color:#003087;color:white;padding:12px;border-radius:10px;text-align:center;font-weight:bold;">🔵 PAYPAL</div></a>''', unsafe_allow_html=True)
        with col_p2:
            if st.button("📱 MOSTRAR QR DEUNA", use_container_width=True):
                # 🚀 SOLUCIÓN DEFINITIVA DE IMAGEN CON BASE64
                directorio_actual = os.path.dirname(os.path.abspath(__file__))
                carpeta_raiz = os.path.dirname(directorio_actual)
                
                # Intentamos buscar en 3 lugares distintos
                posibles_rutas = [
                    os.path.join(carpeta_raiz, "qr_deuna.png"), # Carpeta Principal
                    "qr_deuna.png",                            # Raíz ejecutable
                    os.path.join(directorio_actual, "qr_deuna.png") # Dentro de pages
                ]
                
                ruta_final = None
                for r in posibles_rutas:
                    if os.path.exists(r):
                        ruta_final = r
                        break
                
                if ruta_final:
                    # Leemos la imagen y la convertimos para mostrarla sin errores de ruta
                    with open(ruta_final, "rb") as f:
                        data = base64.b64encode(f.read()).decode()
                    st.markdown(f'<img src="data:image/png;base64,{data}" width="100%">', unsafe_allow_html=True)
                    st.caption(f"WhatsApp: {NUMERO_DEUNA}")
                else:
                    st.error("❌ Archivo 'qr_deuna.png' no encontrado.")
                    st.info(f"Ruta de búsqueda: {carpeta_raiz}")

        if st.button("🔄 YA PAGUÉ, REVISAR MI SALDO", type="primary"):
            res = enviar_datos({"accion": "registrar_pago_deuda", "nombre_completo": f"{user_nom} {user_ape}"})
            if "PAGO_EXITOSO" in res:
                st.success("¡Pago validado!")
                st.rerun()
    else:
        st.metric("💸 Deuda Actual", f"${deuda_actual:.2f}")
        st.progress(min(deuda_actual/DEUDA_MAXIMA, 1.0))

        st.subheader(f"🚦 ESTADO: {st.session_state.datos_usuario.get('Estado', 'OCUPADO')}")
        if st.session_state.datos_usuario.get('Estado') == "LIBRE":
            loc = get_geolocation(component_key='driver_gps')
            if loc:
                lat_now, lon_now = loc['coords']['latitude'], loc['coords']['longitude']
                enviar_datos({"accion": "actualizar_gps_chofer", "conductor": f"{user_nom} {user_ape}", "lat": lat_now, "lon": lon_now})
                if st.session_state.ultima_lat:
                    dist = calcular_distancia(st.session_state.ultima_lat, st.session_state.ultima_lon, lat_now, lon_now)
                    if dist > 0.1:
                        costo = dist * TARIFA_POR_KM
                        enviar_datos({"accion": "registrar_cobro_km", "nombre_completo": f"{user_nom} {user_ape}", "km": dist, "costo": costo})
                        st.session_state.ultima_lat, st.session_state.ultima_lon = lat_now, lon_now
                else: st.session_state.ultima_lat, st.session_state.ultima_lon = lat_now, lon_now

        c1, c2 = st.columns(2)
        with c1:
            if st.button("🟢 PONERME LIBRE", use_container_width=True):
                enviar_datos({"accion": "actualizar_estado", "nombre": user_nom, "apellido": user_ape, "estado": "LIBRE"})
                st.session_state.datos_usuario['Estado'] = "LIBRE"
                st.rerun()
        with c2:
            if st.button("🔴 PONERME OCUPADO", use_container_width=True):
                enviar_datos({"accion": "actualizar_estado", "nombre": user_nom, "apellido": user_ape, "estado": "OCUPADO"})
                st.session_state.datos_usuario['Estado'] = "OCUPADO"
                st.rerun()

    if st.button("🔒 CERRAR SESIÓN"):
        st.session_state.usuario_activo = False
        st.rerun()

else:
    # --- PANTALLA INICIAL: LOGIN Y REGISTRO ---
    tab_log, tab_reg = st.tabs(["🔐 INGRESAR", "📝 REGISTRARME"])
    
    with tab_log:
        col1, col2 = st.columns(2)
        l_nom = col1.text_input("Nombre", key="l_n")
        l_ape = col2.text_input("Apellido", key="l_a")
        l_pass = st.text_input("Contraseña", type="password", key="l_p")
        if st.button("ENTRAR AL PANEL", type="primary"):
            df = cargar_datos("CHOFERES")
            match = df[(df['Nombre'].str.upper() == l_nom.upper()) & (df['Apellido'].str.upper() == l_ape.upper())]
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
            r_ced = st.text_input("Cédula/ID *")
            r_dir = st.text_input("Dirección *")
            r_telf = st.text_input("WhatsApp (Sin código) *")
            r_pla = st.text_input("Placa *")
            r_pass1 = st.text_input("Contraseña *", type="password")
            if st.form_submit_button("✅ COMPLETAR REGISTRO"):
                if r_nom and r_pass1:
                    res = enviar_datos({"accion": "registrar_conductor", "nombre": r_nom, "apellido": r_ape, "cedula": r_ced, "telefono": r_telf, "placa": r_pla, "clave": r_pass1})
                    st.success("¡Registro exitoso! Ve a la pestaña INGRESAR.")
