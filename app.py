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

# AUTO-REFRESCO: Actualiza la app cada 10 segundos
if st.session_state.get('viaje_confirmado', False):
    st_autorefresh(interval=10000, key="datarefresh")

SHEET_ID = "1l3XXIoAggDd2K9PWnEw-7SDlONbtUvpYVw3UYD_9hus"
URL_SCRIPT = "https://script.google.com/macros/s/AKfycbz-mcv2rnAiT10CUDxnnHA8sQ4XK0qLP7Hj2IhnzKp5xz5ugjP04HnQSN7OMvy4-4Al/exec"

# --- 📍 CORRECCIÓN 1: COORDENADAS BASE (EL COCA) ---
# Si el GPS falla, usamos la posición de tu chofer para que la prueba no falle.
LAT_BASE, LON_BASE = -0.6685, -76.8737 

if 'viaje_confirmado' not in st.session_state: st.session_state.viaje_confirmado = False
if 'datos_pedido' not in st.session_state: st.session_state.datos_pedido = {}

# 🎨 ESTILOS CSS
st.markdown("""
    <style>
    .main-title { font-size: 40px; font-weight: bold; text-align: center; color: #000; margin-bottom: 0; }
    .sub-title { font-size: 25px; font-weight: bold; text-align: center; color: #E91E63; margin-top: -10px; margin-bottom: 20px; }
    .stButton>button { width: 100%; height: 50px; font-weight: bold; font-size: 18px; border-radius: 10px; }
    .id-badge { background-color: #F0F2F6; padding: 5px 15px; border-radius: 20px; border: 1px solid #CCC; font-weight: bold; color: #555; display: inline-block; margin-bottom: 10px; }
    .eta-box { background-color: #FFF3E0; padding: 15px; border-radius: 10px; border-left: 5px solid #FF9800; text-align: center; margin-bottom: 15px; font-weight: bold; }
    .footer { text-align: center; color: #888; font-size: 14px; margin-top: 50px; border-top: 1px solid #eee; padding-top: 20px; }
    </style>
""", unsafe_allow_html=True)

# --- 🛠️ FUNCIONES ---

def calcular_distancia_real(lat1, lon1, lat2, lon2):
    """Calcula la distancia en KM entre dos puntos (Haversine)."""
    R = 6371
    dlat, dlon = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)) * R

def obtener_ruta_carretera(lon1, lat1, lon2, lat2):
    """Consulta OSRM para trazar el camino."""
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
        with urllib.request.urlopen(url, timeout=4) as response:
            data = json.loads(response.read().decode())
            return [{"path": data['routes'][0]['geometry']['coordinates']}]
    except:
        return [{"path": [[lon1, lat1], [lon2, lat2]]}]

def cargar_datos(hoja):
    try:
        # Cache busting para asegurar datos frescos
        cb = datetime.now().strftime("%Y%m%d%H%M%S")
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={hoja}&cb={cb}"
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        return df
    except: return pd.DataFrame()

def enviar_datos_a_sheets(datos):
    try:
        params = urllib.parse.urlencode(datos)
        with urllib.request.urlopen(f"{URL_SCRIPT}?{params}") as response:
            return response.read().decode('utf-8')
    except Exception as e: return f"Error: {e}"

def obtener_chofer_mas_cercano(lat_cli, lon_cli, tipo_sol):
    # 1. Cargar ambas tablas
    df_c = cargar_datos("CHOFERES")
    df_u = cargar_datos("UBICACIONES")
    
    if df_c.empty or df_u.empty: return None, None, None, "S/P"
    
    # 2. Normalizar columnas
    df_c.columns = df_c.columns.str.strip().str.upper()
    df_u.columns = df_u.columns.str.strip() 
    
    # 3. Filtrar conductores LIBRES y por TIPO
    tipo_b = tipo_sol.split(" ")[0].upper()
    
    # Asegurar que existan las columnas
    if 'ESTADO' not in df_c.columns or 'TIPO_VEHICULO' not in df_c.columns:
        return None, None, None, "Error Columnas"

    libres = df_c[
        (df_c['ESTADO'].astype(str).str.upper().str.strip() == 'LIBRE') & 
        (df_c['TIPO_VEHICULO'].astype(str).str.upper().str.contains(tipo_b))
    ]

    # 4. Filtro de DEUDA (Opcional)
    if 'DEUDA' in libres.columns:
        libres = libres[pd.to_numeric(libres['DEUDA'], errors='coerce').fillna(0) < 10.00]

    if libres.empty: return None, None, None, "S/P"

    # 5. Buscar el más cercano
    mejor_chofer = None
    menor_distancia = float('inf')

    # Preparar datos de ubicación para búsqueda rápida
    # Asumimos que UBICACIONES tiene col 'Conductor'
    if 'Conductor' in df_u.columns:
        df_u['Conductor_Clean'] = df_u['Conductor'].astype(str).str.strip().str.upper()
    else:
        # Intenta buscar la columna si tiene otro nombre (ej: CONDUCTOR)
        cols_posibles = [c for c in df_u.columns if "CONDUCTOR" in c.upper()]
        if cols_posibles:
            df_u['Conductor_Clean'] = df_u[cols_posibles[0]].astype(str).str.strip().str.upper()
        else:
            return None, None, None, "Error Ubi Cols"

    for _, conductor in libres.iterrows():
        # Construir nombre completo del conductor de la hoja CHOFERES
        nom = str(conductor.get('NOMBRE', '')).strip()
        ape = str(conductor.get('APELLIDO', '')).strip()
        nombre_completo = f"{nom} {ape}".strip().upper()

        # Buscar este nombre en UBICACIONES
        # Tomamos el último registro (iloc[-1])
        ubi_match = df_u[df_u['Conductor_Clean'] == nombre_completo]
        
        if not ubi_match.empty:
            try:
                # Intenta leer Latitud/Longitud (Ajusta nombres si tu Excel es diferente)
                lat_idx = [c for c in ubi_match.columns if "LAT" in c.upper()][0]
                lon_idx = [c for c in ubi_match.columns if "LON" in c.upper()][0]
                
                lat_cond = float(ubi_match.iloc[-1][lat_idx])
                lon_cond = float(ubi_match.iloc[-1][lon_idx])
                
                dist = calcular_distancia_real(lat_cli, lon_cli, lat_cond, lon_cond)
                
                # --- CORRECCIÓN 2: RADIO DE BÚSQUEDA AUMENTADO ---
                # Cambiado de 10 a 10000 km para que SIEMPRE encuentre al conductor en pruebas
                if dist < 10000 and dist < menor_distancia:
                    menor_distancia = dist
                    mejor_chofer = conductor
            except:
                continue

    if mejor_chofer is not None:
        tel = str(mejor_chofer.get('TELEFONO', '0000000000')).split('.')[0].strip()
        foto = str(mejor_chofer.get('FOTO_PERFIL', 'SIN_FOTO'))
        placa = str(mejor_chofer.get('PLACA', 'S/P'))
        return mejor_chofer, tel, foto, placa
        
    return None, None, None, "S/P"

# --- 📱 INTERFAZ ---
st.markdown('<div class="main-title">🚖 TAXI SEGURO</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">🌎 SERVICIO GLOBAL</div>', unsafe_allow_html=True)

loc = get_geolocation()
if loc and 'coords' in loc:
    lat_actual = loc['coords']['latitude']
    lon_actual = loc['coords']['longitude']
else:
    lat_actual, lon_actual = LAT_BASE, LON_BASE
    st.info("📍 Esperando señal GPS... (Usando ubicación base El Coca por ahora)")

if not st.session_state.viaje_confirmado:
    with st.form("form_pedido"):
        nombre_cli = st.text_input("Tu Nombre:")
        celular_input = st.text_input("WhatsApp (Sin código)")
        ref_cli = st.text_input("Referencia / Dirección:")
        tipo_veh = st.selectbox("¿Qué necesitas?", ["Taxi 🚖", "Camioneta 🛻", "Ejecutivo 🚔"])
        enviar = st.form_submit_button("🚖 SOLICITAR UNIDAD")

    if enviar and nombre_cli and ref_cli:
        with st.spinner("🔄 Buscando unidad cercana..."):
            chof, t_chof, foto_chof, placa = obtener_chofer_mas_cercano(lat_actual, lon_actual, tipo_veh)
            
            if chof is not None:
                n_limpio = str(chof['NOMBRE']).strip()
                a_limpio = str(chof['APELLIDO']).strip()
                if a_limpio.lower() == "nan": a_limpio = ""
                nombre_chof = f"{n_limpio} {a_limpio}".strip().upper()
                
                id_v = f"TX-{random.randint(1000, 9999)}"
                # Enviar mapa limpio (sin prefijos) para evitar el error de $7.43 en el futuro
                mapa_url = f"https://www.google.com/maps?q={lat_actual},{lon_actual}"
                
                # 1. Registrar Pedido
                res_pedido = enviar_datos_a_sheets({
                    "accion": "registrar_pedido",
                    "id_viaje": id_v,
                    "cliente": nombre_cli,
                    "tel_cliente": celular_input,
                    "referencia": ref_cli,
                    "conductor": nombre_chof,
                    "tel_conductor": t_chof,
                    "mapa": mapa_url
                })
                
                if "Registrado" in str(res_pedido) or "Ok" in str(res_pedido):
                    # 2. Cambiar estado a OCUPADO
                    enviar_datos_a_sheets({
                        "accion": "cambiar_estado", 
                        "conductor": nombre_chof, 
                        "estado": "OCUPADO"
                    })
                    
                    st.success(f"✅ ¡Conductor encontrado! {n_limpio} va en camino.")
                    st.session_state.viaje_confirmado = True
                    st.session_state.datos_pedido = {
                        "chof": nombre_chof, "t_chof": t_chof, "foto": foto_chof, 
                        "placa": placa, "id": id_v, "mapa": mapa_url, 
                        "lat_cli": lat_actual, "lon_cli": lon_actual, 
                        "nombre": nombre_cli, "ref": ref_cli
                    }
                    import time
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error(f"❌ Error al registrar pedido: {res_pedido}")
            else:
                 st.warning("⚠️ No hay conductores disponibles cerca de tu ubicación en este momento.")

if st.session_state.viaje_confirmado:
    dp = st.session_state.datos_pedido
    
    st.markdown(f'<div style="text-align:center;"><span class="id-badge">🆔 ID: {dp["id"]}</span></div>', unsafe_allow_html=True)
    
    # Foto Conductor
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

    # MAPA DE SEGUIMIENTO EN VIVO
    try:
        df_u = cargar_datos("UBICACIONES")
        
        # Buscar ubicación usando nombre normalizado
        if 'Conductor' in df_u.columns:
             df_u['Conductor_Clean'] = df_u['Conductor'].astype(str).str.strip().str.upper()
        else:
             # Fallback si la columna se llama diferente
             col_name = [c for c in df_u.columns if "CONDUCTOR" in c.upper()][0]
             df_u['Conductor_Clean'] = df_u[col_name].astype(str).str.strip().str.upper()

        pos_t = df_u[df_u['Conductor_Clean'] == str(dp['chof']).strip().upper()]
        
        if not pos_t.empty:
            pos_t = pos_t.iloc[-1]
            # Busqueda dinamica de columnas Lat/Lon
            lat_col = [c for c in df_u.columns if "LAT" in c.upper()][0]
            lon_col = [c for c in df_u.columns if "LON" in c.upper()][0]
            
            lat_t, lon_t = float(pos_t[lat_col]), float(pos_t[lon_col])
            
            dist_km = calcular_distancia_real(lat_t, lon_t, dp['lat_cli'], dp['lon_cli'])
            tiempo_min = round((dist_km / 30) * 60) + 2 
            
            txt_eta = f"Llega en {tiempo_min} min" if tiempo_min > 1 else "¡Llegando!"
            st.markdown(f'<div class="eta-box">🕒 {txt_eta} ({dist_km:.2f} km)</div>', unsafe_allow_html=True)
            
            camino_data = obtener_ruta_carretera(dp['lon_cli'], dp['lat_cli'], lon_t, lat_t)
            
            puntos_mapa = pd.DataFrame([
                {"lon": dp['lon_cli'], "lat": dp['lat_cli'], "color": [0, 128, 0, 200], "radio": 20, "info": "TÚ"},
                {"lon": lon_t, "lat": lat_t, "color": [255, 0, 0, 200], "radio": 20, "info": f"TAXI {dp['placa']}"}
            ])

            st.pydeck_chart(pdk.Deck(
                map_style='https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',
                initial_view_state=pdk.ViewState(latitude=(lat_t + dp['lat_cli'])/2, longitude=(lon_t + dp['lon_cli'])/2, zoom=14, pitch=0),
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
            
    except Exception as e:
        st.error(f"Error cargando mapa: {e}")

st.markdown('<div class="footer">📩 contacto: soporte@taxiseguro.com</div>', unsafe_allow_html=True)
