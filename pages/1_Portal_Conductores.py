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

if 'foto_blindada' not in st.session_state: 
    st.session_state.foto_blindada = None

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
    except Exception as e: 
        return f"Error: {e}"

# --- 📱 INTERFAZ ---
st.title("🚖 Portal de Socios")

if st.session_state.usuario_activo:
    df_fresh = cargar_datos("CHOFERES")
    user_nom = str(st.session_state.datos_usuario['Nombre']).strip()
    user_ape = str(st.session_state.datos_usuario['Apellido']).strip()
    nombre_completo_unificado = f"{user_nom} {user_ape}".upper()
    
    fila_actual = df_fresh[
        (df_fresh['Nombre'].astype(str).str.upper().str.strip() == user_nom.upper()) & 
        (df_fresh['Apellido'].astype(str).str.upper().str.strip() == user_ape.upper())
    ]
    
    st.subheader(f"Bienvenido, {nombre_completo_unificado}")

    foto_mostrar = st.session_state.datos_usuario.get('Foto_Perfil', 'SIN_FOTO')

    if (not foto_mostrar or foto_mostrar == "SIN_FOTO") and not fila_actual.empty:
        foto_excel = fila_actual.iloc[0]['Foto_Perfil']
        if str(foto_excel) != "nan" and len(str(foto_excel)) > 100:
            foto_mostrar = foto_excel
            st.session_state.datos_usuario['Foto_Perfil'] = foto_mostrar

    col_img, col_btn = st.columns([1, 2])
    with col_img:
        if foto_mostrar and str(foto_mostrar) != "nan" and len(str(foto_mostrar)) > 100:
            try:
                img_bytes = base64.b64decode(foto_mostrar)
                st.image(io.BytesIO(img_bytes), width=150)
            except:
                st.image("https://cdn-icons-png.flaticon.com/512/149/149071.png", width=120)
        else:
            st.image("https://cdn-icons-png.flaticon.com/512/149/149071.png", width=120)

    with col_btn:
        st.write("📷 **¿Deseas cambiar tu foto?**")
        archivo_nuevo = st.file_uploader("Sube una imagen (150x150)", type=["jpg", "png", "jpeg"], key="panel_ch_foto")
        
        if archivo_nuevo:
            if st.button("💾 GUARDAR NUEVA FOTO"):
                with st.spinner("Subiendo imagen..."):
                    img = Image.open(archivo_nuevo).convert("RGB")
                    img = img.resize((150, 150)) 
                    buffered = io.BytesIO()
                    img.save(buffered, format="JPEG", quality=60) 
                    foto_b64 = base64.b64encode(buffered.getvalue()).decode()
                    
                    res = enviar_datos({
                        "accion": "actualizar_foto_perfil",
                        "email": fila_actual.iloc[0]['Email'],
                        "foto": foto_b64
                    })
                    
                    if res:
                        st.session_state.datos_usuario['Foto_Perfil'] = foto_b64
                        st.success("✅ ¡Foto actualizada! El cambio es permanente.")

    st.write("---") 
    if st.checkbox("🛰️ ACTIVAR RASTREO GPS", value=True):
        if lat_actual and lon_actual:
            res = enviar_datos({
                "accion": "actualizar_ubicacion",
                "conductor": nombre_completo_unificado,
                "latitud": lat_actual,
                "longitud": lon_actual
            })
            if res:
                st.success(f"📍 Ubicación activa: {lat_actual}, {lon_actual}")
        else:
            st.warning("🛰️ Esperando señal de GPS... Por favor, permite el acceso en tu navegador.")
    
    if not fila_actual.empty:
        deuda_actual = float(fila_actual.iloc[0, 17])
        estado_actual = str(fila_actual.iloc[0, 8]) 
        
        st.info(f"Estado Actual: **{estado_actual}**")
        st.metric("Tu Deuda Actual:", f"${deuda_actual:.2f}")
        st.success(f"✅ Socio: **{nombre_completo_unificado}**")
        
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("💸 Deuda Actual", f"${deuda_actual:.2f}")
        col_m2.metric("🚦 Estado Actual", estado_actual)

        st.subheader("Gestión de Viaje")
        df_viajes = cargar_datos("VIAJES")
        viaje_activo = pd.DataFrame() 

        if not df_viajes.empty and 'Conductor Asignado' in df_viajes.columns:
            viaje_activo = df_viajes[
                (df_viajes['Conductor Asignado'].astype(str).str.upper() == nombre_completo_unificado) & 
                (df_viajes['Estado'].astype(str).str.contains("EN CURSO"))
            ]

        if not viaje_activo.empty:
            datos_v = viaje_activo.iloc[-1]
            st.warning("🚖 TIENES UN PASAJERO A BORDO")
            st.write(f"👤 **Cliente:** {datos_v['Nombre del cliente']}")
            st.write(f"📞 **Tel:** {datos_v['Telefono']}")
            st.write(f"📍 **Destino:** {datos_v['Referencia']}")
            st.markdown(f"[🗺️ Ver Mapa]({datos_v['Mapa']})")

            if st.button("🏁 FINALIZAR VIAJE Y COBRAR", type="primary", use_container_width=True):
                with st.spinner("Calculando distancia real por calles..."):
                    kms_finales = 1.0 
                    if lat_actual and lon_actual:
                        try:
                            link_mapa = str(datos_v['Mapa'])
                            lat_c = float(link_mapa.split('query=')[1].split(',')[0])
                            lon_c = float(link_mapa.split('query=')[1].split(',')[1])
                            url_osrm = f"http://router.project-osrm.org/route/v1/driving/{lon_c},{lat_c};{lon_actual},{lat_actual}?overview=false"
                            res_osrm = requests.get(url_osrm).json()
                            kms_finales = res_osrm['routes'][0]['distance'] / 1000
                            if kms_finales < 0.5: kms_finales = 1.0 
                        except Exception as e:
                            # CORRECCIÓN AQUÍ: Cálculo de respaldo dentro del botón
                            dLat, dLon = radians(lat_actual-lat_c), radians(lon_actual-lon_c)
                            a = sin(dLat/2)**2 + cos(radians(lat_c)) * cos(radians(lat_actual)) * sin(dLon/2)**2
                            kms_finales = 2 * 6371 * asin(sqrt(a))

                    res = enviar_datos({
                        "accion": "terminar_viaje", 
                        "conductor": nombre_completo_unificado,
                        "km": round(kms_finales, 2)
                    })
                    
                    if res:
                        st.success(f"✅ Viaje finalizado: {kms_finales:.2f} km.")
                        time.sleep(2)
                        st.rerun()
        
        st.divider()
        with st.expander("📜 Ver Mi Historial de Viajes"):
            if 'df_viajes' not in locals():
                df_viajes = cargar_datos("VIAJES")
            if not df_viajes.empty and 'Conductor Asignado' in df_viajes.columns:
                mis_viajes = df_viajes[df_viajes['Conductor Asignado'].astype(str).str.upper() == nombre_completo_unificado]
                if not mis_viajes.empty:
                    cols_mostrar = ['Fecha', 'Nombre del cliente', 'Referencia', 'Estado']
                    cols_finales = [c for c in cols_mostrar if c in mis_viajes.columns]
                    st.dataframe(mis_viajes[cols_finales].sort_values(by='Fecha', ascending=False), use_container_width=True)
                else:
                    st.info("Aún no tienes historial de viajes.")
    
    if st.button("🔒 CERRAR SESIÓN"):
        st_javascript("localStorage.removeItem('user_taxi_seguro');")
        st.session_state.usuario_activo = False
        st.rerun()
    st.stop()

else:
    tab_log, tab_reg = st.tabs(["🔐 INGRESAR", "📝 REGISTRARME"])
    # (Resto del código de registro e interfaz sin tocar)
