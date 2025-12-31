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

# AUTO-REFRESCO: Actualiza la app cada 10 segundos para ver el movimiento en vivo
if st.session_state.get('viaje_confirmado', False):
    st_autorefresh(interval=10000, key="datarefresh")

SHEET_ID = "1l3XXIoAggDd2K9PWnEw-7SDlONbtUvpYVw3UYD_9hus"
URL_SCRIPT = "https://script.google.com/macros/s/AKfycbxvsj1h8xSsbyIlo7enfZWO2Oe1IVJer3KHpUO_o08gkRGJKmFnH0wNRvQRa38WWKgv/exec"
LAT_BASE, LON_BASE = -0.466657, -76.989635

if 'viaje_confirmado' not in st.session_state: st.session_state.viaje_confirmado = False
if 'datos_pedido' not in st.session_state: st.session_state.datos_pedido = {}

# 🎨 ESTILOS CSS
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
    """Calcula la distancia en KM entre dos puntos."""
    R = 6371
    dlat, dlon = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)) * R

def obtener_ruta_carretera(lon1, lat1, lon2, lat2):
    """Consulta OSRM para trazar el camino por las calles."""
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
        return df
    except: return pd.DataFrame()

def enviar_datos_a_sheets(datos):
    try:
        params = urllib.parse.urlencode(datos)
        with urllib.request.urlopen(f"{URL_SCRIPT}?{params}") as response:
            return response.read().decode('utf-8')
    except: return "Error"

def obtener_chofer_mas_cercano(lat_cli, lon_cli, tipo_sol):
    df_c, df_u = cargar_datos("CHOFERES"), cargar_datos("UBICACIONES")
    
    # 1. Validaciones básicas
    if df_c.empty or df_u.empty: 
        return None, None, None, "S/P"
    
    tipo_b = tipo_sol.split(" ")[0].upper()
    libres = df_c[(df_c['Estado'].astype(str).str.upper() == 'LIBRE') & (df_c['Tipo_Vehiculo'].astype(str).str.upper().str.contains(tipo_b))]
    
    if libres.empty: 
        return None, None, None, "S/P"

    # 2. Búsqueda por distancia
    mejor, menor = None, float('inf')
    
    for _, chofer in libres.iterrows():
        nom = f"{str(chofer['Nombre']).strip()} {str(chofer['Apellido']).strip()}".upper()
        # Buscamos en UBICACIONES
        ubi = df_u[df_u['Conductor'].astype(str).str.upper().str.strip() == nom]
        
        if not ubi.empty:
            try:
                # Tomamos la última ubicación registrada
                lat_cond = float(ubi.iloc[-1]['Latitud'])
                lon_cond = float(ubi.iloc[-1]['Longitud'])
                d = math.sqrt((lat_cli - lat_cond)**2 + (lon_cli - lon_cond)**2)
                
                if d < menor:
                    menor = d
                    mejor = chofer # Guardamos la FILA completa del chofer
            except (ValueError, TypeError):
                continue
    
    # 3. Procesar datos si encontramos a alguien (LÓGICA UNIVERSAL MEJORADA)
    if mejor is not None:
        # --- LIMPIEZA INTELIGENTE DE TELÉFONO ---
        # 1. Limpieza profunda: Quita .0, espacios y caracteres raros
        raw_t = str(mejor.get('Telefono', '')).split('.')[0].strip()
        t_limpio = re.sub(r"[^0-9+]", "", raw_t) # Deja solo números y el símbolo +
        
        # 2. Validación de seguridad (si está vacío o es muy corto)
        if len(t_limpio) < 5:
            t = "0000000000" 
        else:
            # 3. Formato Inteligente Internacional
            if t_limpio.startswith("+"):
                t = t_limpio.replace("+", "") # WhatsApp usa el número sin el +
            else:
                pais = str(mejor.get('Pais', 'Ecuador')).capitalize().strip()
                # Lista expandible de países
                prefijos = {
                    "Ecuador": "593", "Colombia": "57", "Perú": "51", 
                    "México": "52", "Argentina": "54", "Chile": "56",
                    "España": "34", "Estados Unidos": "1"
                }
                cod = prefijos.get(pais, "593") 
                
                # Regla: Si empieza con 0, lo quitamos y ponemos el prefijo
                if t_limpio.startswith("0"):
                    t = cod + t_limpio[1:]
                # Regla: Si no tiene prefijo, se lo ponemos
                elif not t_limpio.startswith(cod):
                    t = cod + t_limpio
                else:
                    t = t_limpio # Ya tiene el formato correcto

        placa = str(mejor.get('Placa', 'S/P'))
        
        # Devolvemos: (Fila_Chofer, Telefono_Limpio, Foto, Placa)
        return mejor, t, str(mejor['Foto_Perfil']), placa
        
    return None, None, None, "S/P"

# --- 📱 INTERFAZ ---
st.markdown('<div class="main-title">🚖 TAXI SEGURO</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">🌎 SERVICIO GLOBAL</div>', unsafe_allow_html=True)

loc = get_geolocation()
lat_actual, lon_actual = (loc['coords']['latitude'], loc['coords']['longitude']) if loc else (LAT_BASE, LON_BASE)

if not st.session_state.viaje_confirmado:
    with st.form("form_pedido"):
        nombre_cli = st.text_input("Tu Nombre:")
        celular_input = st.text_input("WhatsApp (Sin código)")
        ref_cli = st.text_input("Referencia / Dirección:")
        tipo_veh = st.selectbox("¿Qué necesitas?", ["Taxi 🚖", "Camioneta 🛻", "Ejecutivo 🚔"])
        enviar = st.form_submit_button("🚖 SOLICITAR UNIDAD")

    if enviar and nombre_cli and ref_cli:
        with st.spinner("🔄 Buscando unidad..."):
            # Buscamos al chofer más cercano
            chof, t_chof, foto_chof, placa = obtener_chofer_mas_cercano(lat_actual, lon_actual, tipo_veh)
            
            if chof is not None:
                nombre_chof = f"{chof['Nombre']} {chof['Apellido']}"
                id_v = f"TX-{random.randint(1000, 9999)}"
                mapa_url = f"https://www.google.com/maps?q={lat_actual},{lon_actual}"
                
                # 1. REGISTRO EN HOJA VIAJES (Llenamos columnas A hasta J)
                enviar_datos_a_sheets({
                    "accion": "registrar_pedido", 
                    "cliente": nombre_cli,
                    "tel_cliente": celular_input,  # Dato columna C
                    "referencia": ref_cli, 
                    "mapa": mapa_url,
                    "conductor": nombre_chof,
                    "tel_conductor": t_chof,       # Dato columna I
                    "id_viaje": id_v
                })
                
                # 2. BLOQUEO DE CHOFER (Lo pone OCUPADO)
                enviar_datos_a_sheets({
                    "accion": "cambiar_estado", 
                    "conductor": nombre_chof, 
                    "estado": "OCUPADO"
                }) 
                
                # Guardamos datos en sesión y recargamos
                st.session_state.viaje_confirmado = True
                st.session_state.datos_pedido = {
                    "chof": nombre_chof, 
                    "t_chof": t_chof, 
                    "foto": foto_chof, 
                    "placa": placa, 
                    "id": id_v, 
                    "mapa": mapa_url, 
                    "lat_cli": lat_actual, 
                    "lon_cli": lon_actual, 
                    "nombre": nombre_cli, 
                    "ref": ref_cli
                }
                st.rerun()
            else:
                st.error("❌ No hay unidades libres en este momento.")

if st.session_state.viaje_confirmado:
    dp = st.session_state.datos_pedido
    try:
        df_u = cargar_datos("UBICACIONES")
        # Buscamos al conductor por nombre exacto
        pos_t = df_u[df_u['Conductor'].astype(str).str.upper().str.strip() == str(dp['chof']).upper().strip()]
        
        if not pos_t.empty:
            pos_t = pos_t.iloc[-1] # Tomamos el registro más reciente
            lat_t, lon_t = float(pos_t['Latitud']), float(pos_t['Longitud'])

            # CÁLCULO ETA
            dist_km = calcular_distancia_real(lat_t, lon_t, dp['lat_cli'], dp['lon_cli'])
            tiempo_min = round((dist_km / 30) * 60) + 2 
            txt_eta = f"Llega en aprox. {tiempo_min} min" if tiempo_min > 1 else "¡Llegando!"
            st.markdown(f'<div class="eta-box">🕒 {txt_eta} ({dist_km:.2f} km)</div>', unsafe_allow_html=True)
            
            camino_data = obtener_ruta_carretera(dp['lon_cli'], dp['lat_cli'], lon_t, lat_t)
            
            # Puntos de localización con la VENTANA FLOTANTE activa
            puntos_mapa = pd.DataFrame([
                {"lon": dp['lon_cli'], "lat": dp['lat_cli'], "color": [34, 139, 34], "border": [255, 255, 255], "info": "👤 TÚ (Punto de Encuentro)"},
                {"lon": lon_t, "lat": lat_t, "color": [255, 215, 0], "border": [0, 0, 0], "info": f"🚖 CONDUCTOR: {dp['chof']}\n🏷️ PLACA: {dp['placa']}"}
            ])

            # MAPA
            st.pydeck_chart(pdk.Deck(
                map_style='https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',
                initial_view_state=pdk.ViewState(
                    latitude=lat_t, 
                    longitude=lon_t, 
                    zoom=15, 
                    pitch=0
                ),
                tooltip={"text": "{info}"},
                layers=[
                    pdk.Layer("PathLayer", data=camino_data, get_path="path", get_color=[200, 0, 0, 150], get_width=16, cap_rounded=True),
                    pdk.Layer("PathLayer", data=camino_data, get_path="path", get_color=[255, 0, 0], get_width=8, cap_rounded=True),
                    pdk.Layer(
                        "ScatterplotLayer", 
                        data=puntos_mapa, 
                        get_position="[lon, lat]", 
                        get_color="color", 
                        get_line_color="border", 
                        line_width_min_pixels=1, 
                        get_radius=15, 
                        stroked=True, 
                        pickable=True
                    )
                ]
            ))

            if st.button("🔄 ACTUALIZAR UBICACIÓN"):
                st.rerun()
        else:
            st.warning("📡 Buscando señal del conductor...")

        st.markdown(f'<div style="text-align:center;"><span class="id-badge">🆔 ID: {dp["id"]}</span></div>', unsafe_allow_html=True)
        
        # --- 📸 MOSTRAR FOTO REAL DEL CONDUCTOR ---
        foto_data = dp.get('foto', "SIN_FOTO")

        st.markdown('<div style="text-align:center; margin-bottom:15px;">', unsafe_allow_html=True)
        if foto_data and foto_data != "SIN_FOTO" and len(str(foto_data)) > 100:
            try:
                # Decodifica la imagen Base64
                img_bytes = base64.b64decode(foto_data)
                st.image(io.BytesIO(img_bytes), width=150)
            except:
                st.image("https://cdn-icons-png.flaticon.com/512/149/149071.png", width=130)
        else:
            # Foto por defecto si no hay una guardada
            st.image("https://cdn-icons-png.flaticon.com/512/149/149071.png", width=130)
        st.markdown('</div>', unsafe_allow_html=True)

        st.success(f"✅ Conductor **{dp['chof']}** asignado.")
        
        # Generación del Link de WhatsApp
        msg_wa = urllib.parse.quote(f"🚖 *PEDIDO*\n🆔 *ID:* {dp['id']}\n👤 Cliente: {dp['nombre']}\n📍 Ref: {dp['ref']}\n🗺️ *Mapa:* {dp['mapa']}")
        st.markdown(f'<a href="https://api.whatsapp.com/send?phone={dp["t_chof"]}&text={msg_wa}" target="_blank" style="background-color:#25D366;color:white;padding:15px;text-align:center;display:block;text-decoration:none;font-weight:bold;font-size:20px;border-radius:10px;">📲 CONTACTAR CONDUCTOR</a>', unsafe_allow_html=True)

        if st.button("❌ NUEVO PEDIDO"):
            st.session_state.viaje_confirmado = False
            st.rerun()
            
    except Exception as e: st.info(f"⌛ Recibiendo coordenadas... ({e})")

    st.write("---")
# --- 📧 NOTA INFORMATIVA DE CONTACTO ---
st.markdown(
    """
    <div style="text-align:center; color:#555; font-size:15px; margin-top:10px; font-weight: bold;">
        📩 contacto: taxi-seguro-word@hotmail.com
    </div>
    """, 
    unsafe_allow_html=True
)
