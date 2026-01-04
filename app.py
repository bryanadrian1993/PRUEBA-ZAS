import streamlit as st
import pandas as pd
from streamlit_js_eval import get_geolocation
from datetime import datetime
import urllib.parse
import urllib.request
import json
import random
import math
import pydeck as pdk
from streamlit_autorefresh import st_autorefresh
import io
import base64

# --- ⚙️ CONFIGURACIÓN DEL SISTEMA ---
st.set_page_config(page_title="TAXI SEGURO", page_icon="🚖", layout="centered")

# AUTO-REFRESCO: Actualiza cada 4 seg para mantener el GPS vivo
st_autorefresh(interval=4000, key="client_refresh")

SHEET_ID = "1l3XXIoAggDd2K9PWnEw-7SDlONbtUvpYVw3UYD_9hus"
URL_SCRIPT = "https://script.google.com/macros/s/AKfycbz-mcv2rnAiT10CUDxnnHA8sQ4XK0qLP7Hj2IhnzKp5xz5ugjP04HnQSN7OMvy4-4Al/exec"

if 'viaje_confirmado' not in st.session_state: st.session_state.viaje_confirmado = False
if 'datos_pedido' not in st.session_state: st.session_state.datos_pedido = {}

# 🎨 ESTILOS
st.markdown("""
    <style>
    .main-title { font-size: 32px; font-weight: bold; text-align: center; margin-bottom: 10px; }
    .driver-card { background-color: #f0f2f6; padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
    .stButton>button { width: 100%; height: 55px; font-weight: bold; font-size: 18px; border-radius: 10px; background-color: #ffc107; color: black; border: none; }
    .stButton>button:hover { background-color: #ffca2c; }
    </style>
""", unsafe_allow_html=True)

# --- 🛠️ FUNCIONES ---
def calcular_distancia(lat1, lon1, lat2, lon2):
    try:
        R = 6371
        dlat, dlon = math.radians(lat2-lat1), math.radians(lon2-lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        return 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)) * R
    except: return 0.0

def obtener_ruta(lon1, lat1, lon2, lat2):
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
        with urllib.request.urlopen(url, timeout=2) as r:
            return [{"path": json.loads(r.read().decode())['routes'][0]['geometry']['coordinates']}]
    except: return [{"path": [[lon1, lat1], [lon2, lat2]]}]

def cargar_datos(hoja):
    try:
        cb = datetime.now().strftime("%Y%m%d%H%M%S")
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={hoja}&cb={cb}"
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip().str.upper() # Todo a mayúsculas para evitar errores
        return df
    except: return pd.DataFrame()

def enviar_datos(datos):
    try:
        params = urllib.parse.urlencode(datos)
        with urllib.request.urlopen(f"{URL_SCRIPT}?{params}") as response:
            return response.read().decode('utf-8')
    except: return "Error"

# --- 🔍 BÚSQUEDA INTELIGENTE DE CONDUCTOR ---
def buscar_conductor(lat_cli, lon_cli, tipo_veh):
    df_c = cargar_datos("CHOFERES")
    df_u = cargar_datos("UBICACIONES")
    
    if df_c.empty or df_u.empty: return None

    # Normalizar columna conductor en Ubicaciones
    col_cond_u = next((c for c in df_u.columns if "CONDUCTOR" in c), None)
    if not col_cond_u: return None
    
    df_u['KEY'] = df_u[col_cond_u].astype(str).str.upper().str.strip()
    
    candidatos = []
    tipo_req = tipo_veh.split()[0].upper() # Taxi, Camioneta...

    for _, row in df_c.iterrows():
        # Limpieza profunda de datos
        estado = str(row.get('ESTADO','')).upper().strip()
        vehiculo_row = str(row.get('TIPO_VEHICULO','')).upper()
        
        # Filtro: Debe estar LIBRE y coincidir el tipo de vehiculo
        if "LIBRE" in estado and (tipo_req in vehiculo_row or tipo_req == "TAXI"):
            # Limpieza de nombre (quita 'nan' y espacios)
            nom = str(row.get('NOMBRE','')).replace('nan','').strip()
            ape = str(row.get('APELLIDO','')).replace('nan','').strip()
            nombre_completo = f"{nom} {ape}".upper().strip()
            
            # Buscar GPS de este conductor
            gps_data = df_u[df_u['KEY'] == nombre_completo]
            
            if not gps_data.empty:
                try:
                    # Buscar columnas de lat/lon dinámicamente
                    c_lat = next((c for c in df_u.columns if "LAT" in c), None)
                    c_lon = next((c for c in df_u.columns if "LON" in c), None)
                    
                    if c_lat and c_lon:
                        lat_t = float(gps_data.iloc[-1][c_lat])
                        lon_t = float(gps_data.iloc[-1][c_lon])
                        
                        dist = calcular_distancia(lat_cli, lon_cli, lat_t, lon_t)
                        
                        # Aceptamos conductores en un radio de 5000km (para pruebas)
                        if dist < 5000:
                            candidatos.append({
                                "nombre": nombre_completo,
                                "dist": dist,
                                "placa": str(row.get('PLACA','S/P')),
                                "tel": str(row.get('TELEFONO','')),
                                "foto": str(row.get('FOTO_PERFIL',''))
                            })
                except: pass

    if candidatos:
        candidatos.sort(key=lambda x: x['dist']) # El más cercano primero
        return candidatos[0]
    return None

# --- 🚀 PANTALLA 1: PEDIR TAXI ---
if not st.session_state.viaje_confirmado:
    st.markdown('<div class="main-title">🚖 SOLICITAR UNIDAD</div>', unsafe_allow_html=True)
    
    # GPS
    loc = get_geolocation()
    lat_c, lon_c = None, None
    if loc and 'coords' in loc:
        lat_c = loc['coords']['latitude']
        lon_c = loc['coords']['longitude']
        st.success("📍 Ubicación detectada correctamente")
    else:
        st.warning("⚠️ Activando GPS...")

    with st.form("form_taxi"):
        nombre = st.text_input("Tu Nombre")
        whatsapp = st.text_input("Tu WhatsApp")
        ref = st.text_input("Referencia / Dirección")
        tipo = st.selectbox("Vehículo", ["Taxi 🚖", "Camioneta 🛻", "Ejecutivo 🚔", "Moto 🏍️"])
        
        btn_pedir = st.form_submit_button("📢 PEDIR AHORA")
        
        if btn_pedir:
            if not (nombre and whatsapp and ref and lat_c):
                st.error("Por favor completa los datos y espera al GPS.")
            else:
                with st.spinner("Buscando conductor más cercano..."):
                    mejor = buscar_conductor(lat_c, lon_c, tipo)
                    
                    if mejor:
                        # 1. Registrar en Excel
                        id_viaje = f"TX-{random.randint(1000,9999)}"
                        mapa = f"http://maps.google.com/?q={lat_c},{lon_c}"
                        
                        enviar_datos({
                            "accion": "registrar_pedido", "id_viaje": id_viaje,
                            "cliente": nombre, "tel_cliente": whatsapp, "referencia": ref,
                            "conductor": mejor['nombre'], "tel_conductor": mejor['tel'],
                            "mapa": mapa
                        })
                        
                        # 2. Poner al chofer OCUPADO
                        enviar_datos({"accion": "cambiar_estado", "conductor": mejor['nombre'], "estado": "OCUPADO"})
                        
                        # 3. CAMBIAR DE PANTALLA (Crucial)
                        st.session_state.datos_pedido = {
                            "chof": mejor['nombre'], "placa": mejor['placa'], "tel": mejor['tel'],
                            "foto": mejor['foto'], "id": id_viaje, "lat_c": lat_c, "lon_c": lon_c,
                            "nombre": nombre, "ref": ref, "mapa": mapa
                        }
                        st.session_state.viaje_confirmado = True
                        st.rerun() # <--- ESTO FUERZA LA PANTALLA DE WHATSAPP
                    else:
                        st.error("⚠️ No se encontraron conductores disponibles cerca. Intenta de nuevo.")

# --- 🚀 PANTALLA 2: CONFIRMACIÓN Y MAPA ---
else:
    dp = st.session_state.datos_pedido
    
    st.markdown(f"""
    <div class="driver-card">
        <h3>✅ ¡CONDUCTOR EN CAMINO!</h3>
        <h2 style="color:#000">{dp['chof']}</h2>
        <p style="font-size:18px">Placa: <b>{dp['placa']}</b></p>
    </div>
    """, unsafe_allow_html=True)
    
    # Foto Conductor
    if len(str(dp['foto'])) > 50:
        try: st.image(io.BytesIO(base64.b64decode(dp['foto'])), width=150)
        except: pass
    
    # BOTÓN WHATSAPP GRANDE
    msg = urllib.parse.quote(f"Hola, soy {dp['nombre']}. Te espero en: {dp['ref']}\nUbicación: {dp['mapa']}")
    st.markdown(f'''
        <a href="https://wa.me/593{str(dp['tel']).replace(' ','')}?text={msg}" target="_blank" 
           style="display:block; background-color:#25D366; color:white; text-align:center; padding:18px; border-radius:12px; text-decoration:none; font-weight:bold; font-size:20px; margin-bottom:20px; box-shadow: 0 4px 6px rgba(0,0,0,0.2);">
           📲 ABRIR WHATSAPP
        </a>
    ''', unsafe_allow_html=True)
    
    # Mapa en vivo
    try:
        df_u = cargar_datos("UBICACIONES")
        # Buscar columna conductor
        c_cond = next((c for c in df_u.columns if "CONDUCTOR" in c), None)
        c_lat = next((c for c in df_u.columns if "LAT" in c), None)
        c_lon = next((c for c in df_u.columns if "LON" in c), None)
        
        if c_cond:
            pos = df_u[df_u[c_cond].astype(str).str.strip().str.upper() == dp['chof']]
            if not pos.empty and c_lat:
                lt = float(pos.iloc[-1][c_lat])
                ln = float(pos.iloc[-1][c_lon])
                
                # Pintar mapa
                ruta = obtener_ruta(dp['lon_c'], dp['lat_c'], ln, lt)
                view = pdk.ViewState(latitude=(dp['lat_c']+lt)/2, longitude=(dp['lon_c']+ln)/2, zoom=13)
                
                st.pydeck_chart(pdk.Deck(
                    map_style='https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',
                    initial_view_state=view,
                    layers=[
                        pdk.Layer("PathLayer", data=ruta, get_path="path", get_color=[0,0,255], get_width=5),
                        pdk.Layer("ScatterplotLayer", data=[
                            {"pos": [dp['lon_c'], dp['lat_c']], "c": [0,255,0,200], "r": 20}, # Cliente
                            {"pos": [ln, lt], "c": [255,0,0,200], "r": 20} # Taxi
                        ], get_position="pos", get_fill_color="c", get_radius="r", radius_scale=8)
                    ]
                ))
    except: st.write("Cargando mapa...")

    if st.button("🔄 FINALIZAR / NUEVO"):
        st.session_state.viaje_confirmado = False
        st.rerun()
