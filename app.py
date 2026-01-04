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
from streamlit_autorefresh import st_autorefresh
import io
import base64
from PIL import Image

# --- ⚙️ CONFIGURACIÓN DEL SISTEMA ---
st.set_page_config(page_title="TAXI SEGURO", page_icon="🚖", layout="centered")

# AUTO-REFRESCO: Actualiza la app cada 4 segundos
st_autorefresh(interval=4000, key="datarefresh")

SHEET_ID = "1l3XXIoAggDd2K9PWnEw-7SDlONbtUvpYVw3UYD_9hus"
URL_SCRIPT = "https://script.google.com/macros/s/AKfycbz-mcv2rnAiT10CUDxnnHA8sQ4XK0qLP7Hj2IhnzKp5xz5ugjP04HnQSN7OMvy4-4Al/exec"

if 'viaje_confirmado' not in st.session_state: st.session_state.viaje_confirmado = False
if 'datos_pedido' not in st.session_state: st.session_state.datos_pedido = {}

# 🎨 ESTILOS CSS (TU DISEÑO ORIGINAL EXACTO)
st.markdown("""
    <style>
    .main-title { font-size: 40px; font-weight: bold; text-align: center; color: #000; margin-bottom: 0; }
    .sub-title { font-size: 25px; font-weight: bold; text-align: center; color: #E91E63; margin-top: -10px; margin-bottom: 20px; }
    .step-header { font-size: 18px; font-weight: bold; margin-top: 20px; margin-bottom: 10px; color: #333; }
    .stButton>button { width: 100%; height: 50px; font-weight: bold; font-size: 18px; border-radius: 10px; }
    .id-badge { background-color: #F0F2F6; padding: 5px 15px; border-radius: 20px; border: 1px solid #CCC; font-weight: bold; color: #555; display: inline-block; margin-bottom: 10px; }
    .eta-box { background-color: #FFF3E0; padding: 15px; border-radius: 10px; border-left: 5px solid #FF9800; text-align: center; margin-bottom: 15px; font-weight: bold; }
    .footer { text-align: center; color: #888; font-size: 14px; margin-top: 50px; border-top: 1px solid #eee; padding-top: 20px; }
    </style>
""", unsafe_allow_html=True)

# --- 🛠️ FUNCIONES ---

def calcular_distancia_real(lat1, lon1, lat2, lon2):
    try:
        R = 6371
        dlat, dlon = math.radians(lat2-lat1), math.radians(lon2-lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        return 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)) * R
    except: return 0.0

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
        # --- LIMPIEZA CLAVE: Convertir columnas a mayúsculas y quitar espacios ---
        df.columns = df.columns.str.strip().str.upper()
        return df
    except: return pd.DataFrame()

def enviar_datos_a_sheets(datos):
    try:
        params = urllib.parse.urlencode(datos)
        with urllib.request.urlopen(f"{URL_SCRIPT}?{params}") as response:
            return response.read().decode('utf-8')
    except: return "Error"

def obtener_chofer_mas_cercano(lat_cli, lon_cli, tipo_sol):
    df_c = cargar_datos("CHOFERES")
    df_u = cargar_datos("UBICACIONES")
    
    if df_c.empty or df_u.empty: return None, None, None, "S/P"
    
    tipo_b = tipo_sol.split(" ")[0].upper()

    # Validación de seguridad para columnas
    if 'ESTADO' not in df_c.columns: return None, None, None, "Error Columnas"
    
    libres = df_c[
        (df_c['ESTADO'].astype(str).str.upper().str.strip() == 'LIBRE') & 
        (df_c['TIPO_VEHICULO'].astype(str).str.upper().str.contains(tipo_b))
    ]

    if 'DEUDA' in libres.columns:
        libres = libres[pd.to_numeric(libres['DEUDA'], errors='coerce').fillna(0) < 10.00]

    if libres.empty: return None, None, None, "S/P"

    # --- BÚSQUEDA DINÁMICA DE COLUMNAS EN UBICACIONES ---
    # Esto busca cualquier columna que contenga la palabra clave, sin importar mayúsculas/minúsculas
    col_cond_u = next((c for c in df_u.columns if "CONDUCTOR" in c), None)
    col_lat_u = next((c for c in df_u.columns if "LAT" in c), None)
    col_lon_u = next((c for c in df_u.columns if "LON" in c), None)

    if not (col_cond_u and col_lat_u and col_lon_u): return None, None, None, "Error Ubi Cols"

    # Crear clave de búsqueda limpia
    df_u['KEY'] = df_u[col_cond_u].astype(str).str.strip().str.upper()

    mejor_chofer = None
    menor_distancia = float('inf')

    for _, conductor in libres.iterrows():
        # Limpiar nombre del conductor
        n = str(conductor.get('NOMBRE', '')).replace('nan','').strip()
        a = str(conductor.get('APELLIDO', '')).replace('nan','').strip()
        nombre_completo = f"{n} {a}".strip().upper()

        # Buscar en ubicaciones
        ubi_match = df_u[df_u['KEY'] == nombre_completo]
        
        if not ubi_match.empty:
            try:
                lat_cond = float(ubi_match.iloc[-1][col_lat_u])
                lon_cond = float(ubi_match.iloc[-1][col_lon_u])
                
                dist = calcular_distancia_real(lat_cli, lon_cli, lat_cond, lon_cond)
                
                # Radio aumentado a 10000 km para asegurar que funcione en pruebas
                if dist < 10000 and dist < menor_distancia:
                    menor_distancia = dist
                    mejor_chofer = conductor
            except: continue

    if mejor_chofer is not None:
        t = str(mejor_chofer.get('TELEFONO', '0000000000')).split('.')[0].strip()
        foto = str(mejor_chofer.get('FOTO_PERFIL', 'SIN_FOTO'))
        placa = str(mejor_chofer.get('PLACA', 'S/P'))
        return mejor_chofer, t, foto, placa
        
    return None, None, None, "S/P"

# --- 📱 INTERFAZ ---
st.markdown('<div class="main-title">🚖 TAXI SEGURO</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">🌎 SERVICIO GLOBAL</div>', unsafe_allow_html=True)

# GPS
loc = get_geolocation()
lat_actual, lon_actual = None, None
if loc and 'coords' in loc:
    lat_actual = loc['coords']['latitude']
    lon_actual = loc['coords']['longitude']
    st.success(f"📍 Tu Ubicación: {lat_actual:.5f}, {lon_actual:.5f}")
else:
    st.warning("⚠️ Esperando señal GPS... (Asegúrate de permitir ubicación)")

if not st.session_state.viaje_confirmado:
    with st.form("form_pedido"):
        nombre_cli = st.text_input("Tu Nombre:")
        celular_input = st.text_input("WhatsApp (Sin código)")
        ref_cli = st.text_input("Referencia / Dirección:")
        tipo_veh = st.selectbox("¿Qué necesitas?", ["Taxi 🚖", "Camioneta 🛻", "Ejecutivo 🚔"])
        enviar = st.form_submit_button("🚖 SOLICITAR UNIDAD")

    if enviar:
        if not (nombre_cli and ref_cli and lat_actual):
            if not lat_actual:
                st.error("🚫 NO TENEMOS TU GPS. Por favor activa la ubicación y espera que aparezca en verde.")
            else:
                st.error("Por favor completa los datos.")
        else:
            with st.spinner("🔄 Buscando unidad..."):
                chof, t_chof, foto_chof, placa = obtener_chofer_mas_cercano(lat_actual, lon_actual, tipo_veh)
                
                if chof is not None:
                    # Limpieza final
                    n_clean = str(chof.get('NOMBRE', '')).replace('nan','').strip()
                    a_clean = str(chof.get('APELLIDO', '')).replace('nan','').strip()
                    nombre_chof = f"{n_clean} {a_clean}".strip().upper()
                    
                    id_v = f"TX-{random.randint(1000, 9999)}"
                    mapa_url = f"https://www.google.com/maps?q={lat_actual},{lon_actual}"
                    
                    # 1. Registrar
                    res_pedido = enviar_datos_a_sheets({
                        "accion": "registrar_pedido", "id_viaje": id_v,
                        "cliente": nombre_cli, "tel_cliente": celular_input, "referencia": ref_cli,
                        "conductor": nombre_chof, "tel_conductor": t_chof, "mapa": mapa_url
                    })
                    
                    # 2. Ocupar
                    if "Registrado" in str(res_pedido) or "Ok" in str(res_pedido):
                        enviar_datos_a_sheets({"accion": "cambiar_estado", "conductor": nombre_chof, "estado": "OCUPADO"})
                        
                        # 3. GUARDAR ESTADO Y RECARGAR (SOLUCIÓN A TU PROBLEMA)
                        st.session_state.viaje_confirmado = True
                        st.session_state.datos_pedido = {
                            "chof": nombre_chof, "t_chof": t_chof, "foto": foto_chof, 
                            "placa": placa, "id": id_v, "mapa": mapa_url, 
                            "lat_cli": lat_actual, "lon_cli": lon_actual, 
                            "nombre": nombre_cli, "ref": ref_cli
                        }
                        st.rerun() # <--- ESTO FUERZA EL CAMBIO DE PANTALLA
                    else:
                        st.error("Error conectando con la base de datos.")
                else:
                     st.warning("⚠️ No hay conductores disponibles. Revisa que el conductor esté LIBRE y con el GPS activo.")

if st.session_state.viaje_confirmado:
    dp = st.session_state.datos_pedido
    
    st.markdown(f'<div style="text-align:center;"><span class="id-badge">🆔 ID: {dp["id"]}</span></div>', unsafe_allow_html=True)
    
    foto_data = dp.get('foto', "SIN_FOTO")
    st.markdown('<div style="text-align:center; margin-bottom:15px;">', unsafe_allow_html=True)
    if foto_data and len(str(foto_data)) > 100:
        try:
            img_bytes = base64.b64decode(foto_data)
            st.image(io.BytesIO(img_bytes), width=150)
        except:
            st.image("https://cdn-icons-png.flaticon.com/512/149/149071.png", width=130)
    else:
        st.image("https://cdn-icons-png.flaticon.com/512/149/149071.png", width=130)
    st.markdown('</div>', unsafe_allow_html=True)

    st.success(f"✅ Conductor **{dp['chof']}** asignado.")
    st.info(f"🚗 Vehículo: {dp['placa']}")
    
    msg_wa = urllib.parse.quote(f"🚖 *HOLA TAXI SEGURO*\nSoy {dp['nombre']}\n🆔 ID Viaje: {dp['id']}\n📍 Estoy en: {dp['ref']}\n🗺️ Ver mapa: {dp['mapa']}")
    st.markdown(f'<a href="https://api.whatsapp.com/send?phone={dp["t_chof"]}&text={msg_wa}" target="_blank" style="background-color:#25D366;color:white;padding:15px;text-align:center;display:block;text-decoration:none;font-weight:bold;font-size:20px;border-radius:10px;">📲 CHATEAR CON CONDUCTOR</a>', unsafe_allow_html=True)

    if st.button("❌ CANCELAR / NUEVO PEDIDO"):
        st.session_state.viaje_confirmado = False
        st.rerun()

    st.write("---")

    try:
        df_u = cargar_datos("UBICACIONES")
        # Aseguramos nombres en mayúsculas
        df_u.columns = df_u.columns.str.strip().str.upper()
        
        # Búsqueda dinámica de columna CONDUCTOR
        col_cond = next((c for c in df_u.columns if "CONDUCTOR" in c), None)
        col_lat = next((c for c in df_u.columns if "LAT" in c), None)
        col_lon = next((c for c in df_u.columns if "LON" in c), None)
        
        if col_cond and col_lat and col_lon:
             df_u['KEY_COND'] = df_u[col_cond].astype(str).str.strip().str.upper()
             pos_t = df_u[df_u['KEY_COND'] == str(dp['chof']).strip().upper()]
        
             if not pos_t.empty:
                lt = float(pos_t.iloc[-1][col_lat])
                ln = float(pos_t.iloc[-1][col_lon])
                
                # Calculos de distancia
                dist_km = calcular_distancia_real(lt, ln, dp['lat_cli'], dp['lon_cli'])
                tiempo_min = round((dist_km / 30) * 60) + 2 
                
                txt_eta = f"Llega en {tiempo_min} min" if tiempo_min > 1 else "¡Llegando!"
                st.markdown(f'<div class="eta-box">🕒 {txt_eta} ({dist_km:.2f} km)</div>', unsafe_allow_html=True)
                
                camino_data = obtener_ruta_carretera(dp['lon_cli'], dp['lat_cli'], lon_t, lat_t)
                
                puntos_mapa = pd.DataFrame([
                    {"lon": dp['lon_cli'], "lat": dp['lat_cli'], "color": [34, 139, 34], "info": "TÚ"},
                    {"lon": ln, "lat": lt, "color": [255, 215, 0], "info": f"TAXI {dp['placa']}"}
                ])

                st.pydeck_chart(pdk.Deck(
                    map_style='https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',
                    initial_view_state=pdk.ViewState(latitude=(lat_actual + lt)/2, longitude=(lon_actual + ln)/2, zoom=14, pitch=0),
                    tooltip={"text": "{info}"},
                    layers=[
                        pdk.Layer("PathLayer", data=camino_data, get_path="path", get_color=[0, 0, 255], get_width=5, width_min_pixels=3),
                        pdk.Layer("ScatterplotLayer", data=puntos_mapa, get_position="[lon, lat]", get_fill_color="color", get_radius="radio", pickable=True, radius_scale=6)
                    ]
                ))
                
                if st.button("🔄 ACTUALIZAR MAPA"):
                    st.rerun()
             else:
                st.warning("📡 Esperando señal GPS del conductor...")
        else:
             st.error("⚠️ Error leyendo base de datos de ubicación.")
            
    except Exception as e:
        st.error(f"Error cargando mapa: {e}")

st.markdown('<div class="footer">📩 contacto: soporte@taxiseguro.com</div>', unsafe_allow_html=True)
