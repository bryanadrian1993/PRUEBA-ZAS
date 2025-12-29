import streamlit as st
import pandas as pd
from streamlit_js_eval import get_geolocation
from datetime import datetime
import urllib.parse
import urllib.request
import random
import math
import re
import pydeck as pdk

# --- ⚙️ CONFIGURACIÓN DEL SISTEMA ---
st.set_page_config(page_title="TAXI SEGURO", page_icon="🚖", layout="centered")

# Datos de conexión con Google Sheets
SHEET_ID = "1l3XXIoAggDd2K9PWnEw-7SDlONbtUvpYVw3UYD_9hus"
URL_SCRIPT = "https://script.google.com/macros/s/AKfycbwzOVH8c8f9WEoE4OJOTIccz_EgrOpZ8ySURTVRwi0bnQhFnWVdgfX1W8ivTIu5dFfs/exec"
EMAIL_CONTACTO = "taxi-seguro-world@hotmail.com"

# Ubicación base por defecto (Coca, Ecuador)
LAT_BASE, LON_BASE = -0.466657, -76.989635

# 🎨 ESTILOS PERSONALIZADOS (Interfaz de Usuario)
st.markdown("""
    <style>
    .main-title { font-size: 40px; font-weight: bold; text-align: center; color: #000; margin-bottom: 0; }
    .sub-title { font-size: 25px; font-weight: bold; text-align: center; color: #E91E63; margin-top: -10px; margin-bottom: 20px; }
    .step-header { font-size: 18px; font-weight: bold; margin-top: 20px; margin-bottom: 10px; color: #333; }
    .stButton>button { width: 100%; height: 50px; font-weight: bold; font-size: 18px; border-radius: 10px; }
    .id-badge { background-color: #F0F2F6; padding: 5px 15px; border-radius: 20px; border: 1px solid #CCC; font-weight: bold; color: #555; display: inline-block; margin-bottom: 10px; }
    .footer { text-align: center; color: #888; font-size: 14px; margin-top: 50px; border-top: 1px solid #eee; padding-top: 20px; }
    </style>
""", unsafe_allow_html=True)

# --- 🛠️ FUNCIONES DE DATOS ---

def cargar_datos(hoja):
    """Carga datos y limpia encabezados para evitar el KeyError."""
    try:
        cache_buster = datetime.now().strftime("%Y%m%d%H%M%S")
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={hoja}&cb={cache_buster}"
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip() # Borra espacios ocultos en los nombres de columnas
        return df
    except:
        return pd.DataFrame()

def enviar_datos_a_sheets(datos):
    """Envía la solicitud al Google Apps Script."""
    try:
        params = urllib.parse.urlencode(datos)
        with urllib.request.urlopen(f"{URL_SCRIPT}?{params}") as response:
            return response.read().decode('utf-8')
    except:
        return "Error"

def obtener_chofer_mas_cercano(lat_cli, lon_cli, tipo_sol):
    """Busca la unidad libre más cercana del tipo solicitado."""
    df_c = cargar_datos("CHOFERES")
    df_u = cargar_datos("UBICACIONES")
    if df_c.empty or df_u.empty: return None, None, None
    
    tipo_b = tipo_sol.split(" ")[0].upper()
    libres = df_c[(df_c['Estado'].astype(str).str.upper() == 'LIBRE') & 
                  (df_c['Tipo_Vehiculo'].astype(str).str.upper().str.contains(tipo_b))]
    
    if libres.empty: return None, None, None
    
    mejor, menor = None, float('inf')
    for _, chofer in libres.iterrows():
        nom = f"{chofer['Nombre']} {chofer['Apellido']}"
        ubi = df_u[df_u['Conductor'] == nom]
        if not ubi.empty:
            # Cálculo de distancia
            d = math.sqrt((lat_cli-float(ubi.iloc[-1]['Latitud']))**2 + (lon_cli-float(ubi.iloc[-1]['Longitud']))**2)
            if d < menor:
                menor, mejor = d, chofer
                
    if mejor is not None:
        t = str(mejor['Telefono']).split(".")[0]
        if t.startswith("09"): t = "593" + t[1:]
        return f"{mejor['Nombre']} {mejor['Apellido']}", t, str(mejor['Foto_Perfil'])
    return None, None, None

# --- 📱 INTERFAZ DE USUARIO ---

st.markdown('<div class="main-title">🚖 TAXI SEGURO</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">🌎 SERVICIO GLOBAL</div>', unsafe_allow_html=True)

# Captura de ubicación GPS en tiempo real
loc = get_geolocation()
lat_actual, lon_actual = (loc['coords']['latitude'], loc['coords']['longitude']) if loc else (LAT_BASE, LON_BASE)

with st.form("form_pedido"):
    nombre_cli = st.text_input("Tu Nombre:")
    st.write("Tu Número de WhatsApp:")
    c1, c2 = st.columns([1.5, 3])
    prefijo = c1.selectbox("País", ["+593 (Ecuador)", "+57 (Colombia)", "+51 (Perú)", "+1 (USA)"])
    celular = c2.text_input("Número (Sin el código de país)")
    ref_cli = st.text_input("Referencia / Dirección:")
    tipo_veh = st.selectbox("¿Qué necesitas?", ["Taxi 🚖", "Camioneta 🛻", "Ejecutivo 🚔"])
    enviar = st.form_submit_button("🚖 SOLICITAR UNIDAD")

if enviar:
    if not nombre_cli or not ref_cli or not celular:
        st.error("⚠️ Todos los campos son obligatorios para procesar tu solicitud.")
    else:
        with st.spinner("🔄 Conectando con Google Maps y buscando unidad..."):
            chof, t_chof, foto_chof = obtener_chofer_mas_cercano(lat_actual, lon_actual, tipo_veh)
            id_v = f"TX-{random.randint(1000, 9999)}"
            
            if chof:
                st.balloons()
                
                # --- 🗺️ SISTEMA DE RASTREO ESTILO GOOGLE MAPS (PYDECK) ---
                # Esta sección muestra el mapa con calles, edificios y perspectiva 3D.
                try:
                    df_u = cargar_datos("UBICACIONES")
                    # Obtenemos la última señal GPS del taxi asignado
                    pos_t = df_u[df_u['Conductor'] == chof].iloc[-1]
                    lat_t, lon_t = float(pos_t['Latitud']), float(pos_t['Longitud'])

                    st.markdown('<div class="step-header">📍 RASTREO EN TIEMPO REAL</div>', unsafe_allow_html=True)
                    
                    # Marcadores: Verde (Cliente), Rojo (Taxi)
                    puntos_df = pd.DataFrame([
                        {"lon": lon_actual, "lat": lat_actual, "color": [34, 139, 34, 255], "tag": "Tu Ubicación"},
                        {"lon": lon_t, "lat": lat_t, "color": [220, 20, 60, 255], "tag": f"Taxi: {chof}"}
                    ])

                    # Capa de Puntos (Scatterplot)
                    capa_puntos = pdk.Layer(
                        "ScatterplotLayer",
                        data=puntos_df,
                        get_position="[lon, lat]",
                        get_color="color",
                        get_radius=300, # Tamaño visible en zoom de ciudad
                        pickable=True
                    )
                    
                    # Capa de Línea (Ruta Directa)
                    capa_ruta = pdk.Layer(
                        "LineLayer",
                        data=[{"s": [lon_actual, lat_actual], "e": [lon_t, lat_t]}],
                        get_source_position="s",
                        get_target_position="e",
                        get_color=[70, 130, 180, 200], # Azul Google Maps
                        get_width=15
                    )

                    # Configuración de mapa idéntica a la navegación de Google Maps
                    st.pydeck_chart(pdk.Deck(
                        map_style='road', # Activa calles, avenidas y nombres
                        initial_view_state=pdk.ViewState(
                            latitude=(lat_actual + lat_t) / 2, 
                            longitude=(lon_actual + lon_t) / 2, 
                            zoom=15, # Zoom cercano para ver calles
                            pitch=45 # Perspectiva 3D
                        ),
                        layers=[capa_ruta, capa_puntos],
                        tooltip={"text": "{tag}"}
                    ))

                    if st.button("🔄 ACTUALIZAR MOVIMIENTO"):
                        st.rerun() # Actualiza la posición del taxi en el mapa

                except Exception:
                    st.info("⌛ Iniciando mapa... Los puntos aparecerán cuando el conductor envíe su señal.")

                # --- INFORMACIÓN DEL CONDUCTOR ---
                st.markdown(f'<div style="text-align:center;"><span class="id-badge">🆔 ID VIAJE: {id_v}</span></div>', unsafe_allow_html=True)
                
                # Visualización de foto de perfil circular
                if foto_chof and "http" in foto_chof:
                    id_f = re.search(r'[-\w]{25,}', foto_chof).group() if re.search(r'[-\w]{25,}', foto_chof) else ""
                    if id_f:
                        st.markdown(f'<div style="text-align:center; margin-bottom:15px;"><img src="https://lh3.googleusercontent.com/u/0/d/{id_f}" style="width:130px;height:130px;border-radius:50%;object-fit:cover;border:4px solid #25D366;box-shadow: 0 4px 8px rgba(0,0,0,0.2);"></div>', unsafe_allow_html=True)

                st.success(f"✅ ¡Unidad Encontrada! Conductor: **{chof}**")
                
                # Botón de contacto directo por WhatsApp
                msg_wa = urllib.parse.quote(f"🚖 *PEDIDO TAXI SEGURO*\n🆔 *ID:* {id_v}\n👤 Cliente: {nombre_cli}\n📍 Ref: {ref_cli}")
                st.markdown(f'<a href="https://api.whatsapp.com/send?phone={t_chof}&text={msg_wa}" target="_blank" style="background-color:#25D366;color:white;padding:15px;text-align:center;display:block;text-decoration:none;font-weight:bold;font-size:20px;border-radius:10px;">📲 ENVIAR MI UBICACIÓN POR WHATSAPP</a>', unsafe_allow_html=True)
            
            else:
                st.error("❌ En este momento no hay unidades disponibles de este tipo cerca de tu ubicación.")

st.markdown('<div class="footer"><p>© 2025 Taxi Seguro Global - Servicio al Cliente</p></div>', unsafe_allow_html=True)
