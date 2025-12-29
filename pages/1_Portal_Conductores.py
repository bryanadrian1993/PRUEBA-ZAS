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
import pydeck as pdk
from streamlit_autorefresh import st_autorefresh

# --- ⚙️ CONFIGURACIÓN DE NEGOCIO ---
TARIFA_POR_KM = 0.05        
DEUDA_MAXIMA = 10.00        
LINK_PAYPAL = "https://paypal.me/CAMPOVERDEJARAMILLO" 
NUMERO_DEUNA = "09XXXXXXXX" 

# --- 🔗 CONFIGURACIÓN TÉCNICA ---
st.set_page_config(page_title="Portal Conductores", page_icon="🚖", layout="centered")

# Auto-refresco cada 10 segundos para seguimiento en vivo si el usuario está activo
if st.session_state.get('usuario_activo', False):
    st_autorefresh(interval=10000, key="driver_refresh")

SHEET_ID = "1l3XXIoAggDd2K9PWnEw-7SDlONbtUvpYVw3UYD_9hus"
# ✅ TU NUEVA URL DE SCRIPT INTEGRADA AQUÍ:
URL_SCRIPT = "https://script.google.com/macros/s/AKfycbzivwxOGYSA33ekluigM6o6ZwwmavUKnzmEMxBUftKYqbblGGvbbYomci2qJE8zuYZi/exec"

# --- 🔄 INICIALIZAR SESIÓN ---
if 'usuario_activo' not in st.session_state: st.session_state.usuario_activo = False
if 'datos_usuario' not in st.session_state: st.session_state.datos_usuario = {}
if 'ultima_lat' not in st.session_state: st.session_state.ultima_lat = None
if 'ultima_lon' not in st.session_state: st.session_state.ultima_lon = None

# --- 📋 LISTAS ---
PAISES = ["Ecuador", "Colombia", "Perú", "México", "España", "Estados Unidos", "Argentina", "Brasil", "Chile", "Otro"]
VEHICULOS = ["Taxi 🚖", "Camioneta 🛻", "Ejecutivo 🚔", "Moto Entrega 🏍️"]

# --- 🛠️ FUNCIONES ---
def cargar_datos(hoja):
    try:
        cache_buster = datetime.now().strftime("%Y%m%d%H%M%S")
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={hoja}&cb={cache_buster}"
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        return df
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
    return 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)) R

# --- 📱 INTERFAZ ---
st.title("🚖 Portal de Socios")

if st.session_state.usuario_activo:
    # --- PANEL DEL CONDUCTOR LOGUEADO ---
    df_fresh = cargar_datos("CHOFERES")
    user_nom = st.session_state.datos_usuario['Nombre']
    user_ape = st.session_state.datos_usuario['Apellido']
    fila_actual = df_fresh[(df_fresh['Nombre'] == user_nom) & (df_fresh['Apellido'] == user_ape)]
    
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
                directorio_actual = os.path.dirname(os.path.abspath(__file__))
                ruta_final = os.path.join(directorio_actual, "qr_deuna.png")
                if os.path.exists(ruta_final):
                    with open(ruta_final, "rb") as f:
                        data = base64.b64encode(f.read()).decode()
                    st.markdown(f'<img src="data:image/png;base64,{data}" width="100%">', unsafe_allow_html=True)
                else:
                    st.error("❌ Archivo QR no encontrado.")

        if st.button("🔄 YA PAGUÉ, REVISAR MI SALDO", type="primary"):
            res = enviar_datos({"accion": "registrar_pago_deuda", "nombre_completo": f"{user_nom} {user_ape}"})
            if "PAGO_EXITOSO" in res:
                st.success("¡Pago validado!")
                st.rerun()
    else:
        st.metric("💸 Deuda Actual", f"${deuda_actual:.2f}")
        st.progress(min(deuda_actual/DEUDA_MAXIMA, 1.0))

        st.subheader(f"🚦 ESTADO: {st.session_state.datos_usuario.get('Estado', 'OCUPADO')}")
        
        loc = get_geolocation(component_key='driver_gps')
        if loc:
            lat_t, lon_t = loc['coords']['latitude'], loc['coords']['longitude']
            
            if st.session_state.datos_usuario.get('Estado') == "LIBRE":
                enviar_datos({"accion": "actualizar_gps_chofer", "conductor": f"{user_nom} {user_ape}", "lat": lat_t, "lon": lon_t})
                if st.session_state.ultima_lat:
                    dist = calcular_distancia(st.session_state.ultima_lat, st.session_state.ultima_lon, lat_t, lon_t)
                    if dist > 0.05:
                        costo = dist * TARIFA_POR_KM
                        enviar_datos({"accion": "registrar_cobro_km", "nombre_completo": f"{user_nom} {user_ape}", "km": dist, "costo": costo})
                        st.session_state.ultima_lat, st.session_state.ultima_lon = lat_t, lon_t
                else: st.session_state.ultima_lat, st.session_state.ultima_lon = lat_t, lon_t

            # --- MAPA DE RASTREO (BLOQUEADO Y CENTRADO) ---
            puntos_mapa = pd.DataFrame([
                {"lon": lon_t, "lat": lat_t, "color": [255, 215, 0], "info": f"🚖 {user_nom} {user_ape}\n🏷️ MI POSICIÓN"}
            ])

            st.pydeck_chart(pdk.Deck(
                map_style='https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',
                initial_view_state=pdk.ViewState(latitude=lat_t, longitude=lon_t, zoom=16, pitch=0),
                tooltip={"text": "{info}"},
                layers=[
                    pdk.Layer(
                        "ScatterplotLayer", 
                        data=puntos_mapa, 
                        get_position="[lon, lat]", 
                        get_color="color", 
                        get_radius=15, 
                        pickable=False # BLOQUEO TOTAL DE PUNTOS
                    )
                ]
            ))

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

        if st.button("🔄 ACTUALIZAR UBICACIÓN", use_container_width=True):
            st.rerun()

    if st.button("🔒 CERRAR SESIÓN"):
        st.session_state.usuario_activo = False
        st.rerun()

else:
    # --- PANTALLA INICIAL ---
    tab_log, tab_reg, tab_rec = st.tabs(["🔐 INGRESAR", "📝 REGISTRARME", "🔑 RECUPERAR"])
    
    with tab_log:
        col1, col2 = st.columns(2)
        l_nom = col1.text_input("Nombre", key="l_n")
        l_ape = col2.text_input("Apellido", key="l_a")
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
            st.subheader("Registro de Nuevos Socios")
            r_nom = st.text_input("Nombres *")
            r_ape = st.text_input("Apellidos *")
            r_email = st.text_input("Email (Correo Electrónico) *")
            r_ced = st.text_input("Cédula/ID *")
            r_telf = st.text_input("WhatsApp (Sin código) *")
            r_pla = st.text_input("Placa *")
            r_pass1 = st.text_input("Contraseña *", type="password")
            if st.form_submit_button("✅ COMPLETAR REGISTRO"):
                if r_nom and r_ape and r_email and r_pass1:
                    if not re.match(r"[^@]+@[^@]+\.[^@]+", r_email):
                        st.error("Email inválido")
                    else:
                        enviar_datos({"accion": "registrar_conductor", "nombre": r_nom, "apellido": r_ape, "email": r_email, "cedula": r_ced, "telefono": r_telf, "placa": r_pla, "clave": r_pass1})
                        st.success("¡Registrado! Ya puedes ingresar.")
                else: st.warning("Faltan campos")

    with tab_rec:
        st.subheader("Recuperar Cuenta")
        st.info("Ingresa tu email registrado. Te enviaremos tus credenciales al correo.")
        rec_email = st.text_input("Tu Correo Electrónico", key="email_rec")
        if st.button("✉️ ENVIAR MIS DATOS AL CORREO"):
            if rec_email:
                with st.spinner("Enviando..."):
                    res = enviar_datos({"accion": "recuperar_por_correo", "email": rec_email})
                    if res == "CORREO_ENVIADO":
                        st.success(f"✅ Enviado con éxito a: {rec_email}")
                        st.balloons()
                    else: st.error("❌ Correo no encontrado.")

st.markdown('<div class="footer"><p>© 2025 Taxi Seguro Global</p></div>', unsafe_allow_html=True)
