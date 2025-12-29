import streamlit as st
import pandas as pd
from streamlit_js_eval import get_geolocation
from datetime import datetime
import urllib.parse
import urllib.request
import json
import random
import math
import re
import pydeck as pdk
import base64
import os
from streamlit_autorefresh import st_autorefresh

# --- ⚙️ CONFIGURACIÓN DEL SISTEMA ---
st.set_page_config(page_title="TAXI SEGURO", page_icon="🚖", layout="centered")

# Auto-refresco cada 10 segundos si hay un viaje activo para ver el taxi moverse
if st.session_state.get('viaje_confirmado', False):
    st_autorefresh(interval=10000, key="datarefresh")

SHEET_ID = "1l3XXIoAggDd2K9PWnEw-7SDlONbtUvpYVw3UYD_9hus"
URL_SCRIPT = "https://script.google.com/macros/s/AKfycbwmdasUK1xYWaJjk-ytEAjepFazngTZ91qxhsuN0VZ0OgQmmjyZnD6nOnCNuwIL3HjD/exec"
LAT_BASE, LON_BASE = -0.466657, -76.989635

# --- 🛠️ FUNCIONES ---

def calcular_distancia_real(lat1, lon1, lat2, lon2):
    R = 6371
    dlat, dlon = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)) * R

def obtener_ruta_carretera(lon1, lat1, lon2, lat2):
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
        with urllib.request.urlopen(url, timeout=4) as response:
            data = json.loads(response.read().decode())
            return [{"path": data['routes'][0]['geometry']['coordinates']}]
    except:
        return [{"path": [[lon1, lat1], [lon2, lat2]]}]

def cargar_datos(hoja):
    try:
        cb = datetime.now().strftime("%Y%m%d%H%M%S")
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={hoja}&cb={cb}"
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        # Limpieza de espacios para asegurar coincidencias de nombres
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        return df
    except: return pd.DataFrame()

def enviar_datos(datos):
    try:
        params = urllib.parse.urlencode(datos)
        with urllib.request.urlopen(f"{URL_SCRIPT}?{params}") as response:
            return response.read().decode('utf-8')
    except: return "Error"

def obtener_chofer_mas_cercano(lat_cli, lon_cli, tipo_sol):
    df_c = cargar_datos("CHOFERES")
    df_u = cargar_datos("UBICACIONES")
    if df_c.empty or df_u.empty: return None, None, None, "S/P"

    # ✅ Búsqueda flexible para Camionetas (ignora emojis)
    tipo_key = tipo_sol.split(" ")[0].upper()
    
    libres = df_c[
        (df_c['Estado'].astype(str).str.upper() == 'LIBRE') & 
        (df_c['Tipo_Vehiculo'].astype(str).str.upper().str.contains(tipo_key, na=False))
    ]
    
    mejor, menor = None, float('inf')
    for _, chofer in libres.iterrows():
        nombre_c = f"{chofer['Nombre']} {chofer['Apellido']}".upper()
        ubi = df_u[df_u['Conductor'].str.upper() == nombre_c]
        
        if not ubi.empty:
            try:
                c_lat, c_lon = float(ubi.iloc[-1]['Latitud']), float(ubi.iloc[-1]['Longitud'])
                d = math.sqrt((lat_cli - c_lat)**2 + (lon_cli - c_lon)**2)
                if d < menor: menor, mejor = d, chofer
            except: continue
            
    if mejor is not None:
        t_limpio = re.sub(r'\D', '', str(mejor['Telefono']).split(".")[0])
        return f"{mejor['Nombre']} {mejor['Apellido']}", t_limpio, str(mejor['Foto_Perfil']), str(mejor['Placa'])
    return None, None, None, "S/P"

# --- 📱 INTERFAZ ---
st.markdown('<h1 style="text-align:center;">🚖 TAXI SEGURO</h1>', unsafe_allow_html=True)

# --- SECCIÓN SOCIOS (LOGIN ACTIVO) ---
if st.session_state.get('usuario_activo', False):
    df_fresh = cargar_datos("CHOFERES")
    user_nom = st.session_state.datos_usuario['Nombre']
    user_ape = st.session_state.datos_usuario['Apellido']
    fila = df_fresh[(df_fresh['Nombre'] == user_nom) & (df_fresh['Apellido'] == user_ape)]
    
    if not fila.empty:
        deuda = float(fila.iloc[0, 17])
        st.success(f"✅ Socio: **{user_nom} {user_ape}**")
        st.metric("💸 Deuda Actual", f"${deuda:.2f}")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🟢 PONERME LIBRE", use_container_width=True):
                enviar_datos({"accion": "actualizar_estado", "nombre": user_nom, "apellido": user_ape, "estado": "LIBRE"})
                st.rerun()
        with col2:
            if st.button("🔴 PONERME OCUPADO", use_container_width=True):
                enviar_datos({"accion": "actualizar_estado", "nombre": user_nom, "apellido": user_ape, "estado": "OCUPADO"})
                st.rerun()
    
    if st.button("🔒 CERRAR SESIÓN"):
        st.session_state.usuario_activo = False
        st.rerun()

# --- SECCIÓN CLIENTES (PEDIDOS) ---
else:
    loc = get_geolocation()
    lat_act, lon_act = (loc['coords']['latitude'], loc['coords']['longitude']) if loc else (LAT_BASE, LON_BASE)

    if not st.session_state.get('viaje_confirmado', False):
        with st.form("form_pedido"):
            nombre_cli = st.text_input("Tu Nombre:")
            ref_cli = st.text_input("Dirección / Referencia:")
            tipo_veh = st.selectbox("¿Qué necesitas?", ["Taxi 🚖", "Camioneta 🛻", "Ejecutivo 🚔"])
            if st.form_submit_button("🚖 SOLICITAR UNIDAD"):
                chof, tel, foto, placa = obtener_chofer_mas_cercano(lat_act, lon_act, tipo_veh)
                if chof:
                    id_v = f"TX-{random.randint(1000, 9999)}"
                    st.session_state.viaje_confirmado = True
                    st.session_state.datos_pedido = {"chof": chof, "tel": tel, "placa": placa, "id": id_v, "lat_cli": lat_act, "lon_cli": lon_act}
                    st.rerun()
                else:
                    st.error("❌ No hay unidades libres de este tipo.")

    if st.session_state.get('viaje_confirmado', False):
        dp = st.session_state.datos_pedido
        try:
            df_u = cargar_datos("UBICACIONES")
            pos_t = df_u[df_u['Conductor'].str.upper() == dp['chof'].upper()].iloc[-1]
            lat_t, lon_t = float(pos_t['Latitud']), float(pos_t['Longitud'])

            st.info(f"🆔 Viaje: {dp['id']} | Conductor: {dp['chof']} | Placa: {dp['placa']}")
            
            # Mapa de Seguimiento
            camino = obtener_ruta_carretera(dp['lon_cli'], dp['lat_cli'], lon_t, lat_t)
            st.pydeck_chart(pdk.Deck(
                initial_view_state=pdk.ViewState(latitude=lat_t, longitude=lon_t, zoom=15),
                layers=[
                    pdk.Layer("PathLayer", data=camino, get_path="path", get_color=[255, 0, 0], get_width=5),
                    pdk.Layer("ScatterplotLayer", data=[{"lon": lon_t, "lat": lat_t}], get_position="[lon, lat]", get_color=[255, 215, 0], get_radius=30)
                ]
            ))
            
            if st.button("❌ CANCELAR / NUEVO PEDIDO"):
                st.session_state.viaje_confirmado = False
                st.rerun()
        except: st.info("⌛ Esperando señal GPS del conductor...")

st.markdown('<div style="text-align:center; color:#888; font-size:12px; margin-top:50px; border-top:1px solid #eee; padding-top:10px;">© 2025 Taxi Seguro Global</div>', unsafe_allow_html=True)
