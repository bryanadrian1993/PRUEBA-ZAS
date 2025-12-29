import streamlit as st
import pandas as pd
from streamlit_js_eval import get_geolocation
from datetime import datetime
import urllib.parse
import urllib.request
import random
import math

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="TAXI SEGURO", page_icon="🚖", layout="centered")

# 🆔 CONEXIÓN
SHEET_ID = "1l3XXIoAggDd2K9PWnEw-7SDlONbtUvpYVw3UYD_9hus"
URL_SCRIPT = "https://script.google.com/macros/s/AKfycbwzOVH8c8f9WEoE4OJOTIccz_EgrOpZ8ySURTVRwi0bnQhFnWVdgfX1W8ivTIu5dFfs/exec"
EMAIL_CONTACTO = "taxi-seguro-world@hotmail.com"

# Coordenadas base (solo por si el GPS falla al inicio, apunta a Coca, Ecuador)
LAT_BASE = -0.466657
LON_BASE = -76.989635

# 🎨 ESTILOS
st.markdown("""
    <style>
    .main-title { font-size: 40px; font-weight: bold; text-align: center; color: #000; margin-bottom: 0; }
    .sub-title { font-size: 25px; font-weight: bold; text-align: center; color: #E91E63; margin-top: -10px; margin-bottom: 20px; }
    .step-header { font-size: 18px; font-weight: bold; margin-top: 20px; margin-bottom: 10px; color: #333; }
    .stButton>button { width: 100%; height: 50px; font-weight: bold; font-size: 18px; border-radius: 10px; }
    .id-badge { background-color: #F0F2F6; padding: 5px 15px; border-radius: 20px; border: 1px solid #CCC; font-weight: bold; color: #555; display: inline-block; margin-bottom: 10px; }
    .footer { text-align: center; color: #888; font-size: 14px; margin-top: 50px; border-top: 1px solid #eee; padding-top: 20px; }
    .footer a { color: #E91E63; text-decoration: none; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- FÓRMULA DISTANCIA ---
def calcular_distancia(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2) * math.sin(dlat/2) + math.cos(math.radians(lat1)) \
        * math.cos(math.radians(lat2)) * math.sin(dlon/2) * math.sin(dlon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

# --- FUNCIONES ---
def cargar_datos(hoja):
    try:
        cache_buster = datetime.now().strftime("%Y%m%d%H%M%S")
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={hoja}&cb={cache_buster}"
        return pd.read_csv(url)
    except: return pd.DataFrame()

def enviar_datos_a_sheets(datos):
    try:
        params = urllib.parse.urlencode(datos)
        url_final = f"{URL_SCRIPT}?{params}"
        with urllib.request.urlopen(url_final) as response:
            return response.read().decode('utf-8')
    except Exception as e: return f"Error: {e}"

# === LÓGICA INTERNACIONAL INTELIGENTE ===
def formatear_internacional(prefijo, numero):
    if not numero: return ""
    # 1. Limpiar el número (quitar espacios, guiones, letras, puntos)
    n = str(numero).split(".")[0].strip()
    n = ''.join(filter(str.isdigit, n))
    
    # 2. Limpiar el prefijo (quitar el + y paréntesis) -> Ej: "+593 (Ecuador)" queda "593"
    p = str(prefijo).split(" ")[0].replace("+", "").strip()
    
    # 3. Validaciones especiales por país
    # Si el usuario ya puso el código de país al inicio, no lo repetimos
    if n.startswith(p):
        return n 
    
    # ARGENTINA: A veces necesitan un 9 después del 54 para móviles (54 9 ...)
    if p == "54" and not n.startswith("9"):
        # Opcional: Podríamos forzar el 9, pero dejemos que WhatsApp lo intente estándar primero
        pass 

    # Quitamos el '0' inicial si existe (Común en Ecu, Col, UK)
    if n.startswith("0"):
        n = n[1:]
        
    return p + n

def obtener_chofer_mas_cercano(lat_cliente, lon_cliente):
    df_choferes = cargar_datos("CHOFERES")
    df_ubicaciones = cargar_datos("UBICACIONES")
    
    if df_choferes.empty or df_ubicaciones.empty: return None, None, None

    if 'Estado' in df_choferes.columns:
        libres = df_choferes[df_choferes['Estado'].astype(str).str.strip().str.upper() == 'LIBRE']
        if libres.empty: return None, None, None
            
        mejor_chofer = None
        menor_distancia = float('inf')
        
        for index, chofer in libres.iterrows():
            nombre_completo = f"{chofer['Nombre']} {chofer['Apellido']}"
            ubi = df_ubicaciones[df_ubicaciones['Conductor'] == nombre_completo]
            if not ubi.empty:
                lat_chof = float(ubi.iloc[-1]['Latitud'])
                lon_chof = float(ubi.iloc[-1]['Longitud'])
                dist = calcular_distancia(lat_cliente, lon_cliente, lat_chof, lon_chof)
                if dist < menor_distancia:
                    menor_distancia = dist
                    mejor_chofer = chofer
        
        if mejor_chofer is not None:
            foto = ""
            try:
                if 'FOTO_PENDIENTE' in mejor_chofer: foto = str(mejor_chofer['FOTO_PENDIENTE'])
                else: foto = str(mejor_chofer.iloc[11]) 
            except: pass
            
            # Recuperamos el teléfono del chofer (se asume que en el registro ya se guardó bien o se corregirá)
            # Para estar seguros, si no tiene código y parece de Ecuador, le ponemos 593
            telf = str(mejor_chofer['Telefono']).split(".")[0].strip()
            telf_limpio = ''.join(filter(str.isdigit, telf))
            
            # Parche de seguridad para choferes antiguos que se registraron sin código
            if len(telf_limpio) == 9 and telf_limpio.startswith("09"): # Ecuador típico
                telf_limpio = "593" + telf_limpio[1:]
            elif len(telf_limpio) == 10 and telf_limpio.startswith("09"): # Ecuador con 0
                telf_limpio = "593" + telf_limpio[1:]
                
            return f"{mejor_chofer['Nombre']} {mejor_chofer['Apellido']}", telf_limpio, foto
            
    return None, None, None

# --- INTERFAZ CLIENTE ---
st.markdown('<div class="main-title">🚖 TAXI SEGURO</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">🌎 SERVICIO GLOBAL</div>', unsafe_allow_html=True)
st.sidebar.info("👋 **Conductores:**\nUsen el menú de navegación para ir al Portal de Socios.")
st.divider()

st.markdown('<div class="step-header">📡 PASO 1: ACTIVAR UBICACIÓN</div>', unsafe_allow_html=True)
loc = get_geolocation()
lat_actual, lon_actual = LAT_BASE, LON_BASE
if loc:
    lat_actual = loc['coords']['latitude']
    lon_actual = loc['coords']['longitude']
    mapa = f"https://www.google.com/maps?q={lat_actual},{lon_actual}"
    st.success("✅ GPS ACTIVADO")
else:
    mapa = "No detectado"
    st.info("📍 Por favor activa tu GPS.")

st.markdown('<div class="step-header">📝 PASO 2: DATOS DEL VIAJE</div>', unsafe_allow_html=True)
with st.form("form_pedido"):
    nombre_cli = st.text_input("Tu Nombre:")
    
    # === SELECCIÓN DE PAÍS COMPLETA ===
    st.write("Tu Número de WhatsApp:")
    col_pref, col_num = st.columns([1.5, 3])
    
    # LISTA IDÉNTICA AL REGISTRO DE CONDUCTORES
    prefijo_pais = col_pref.selectbox("País", [
        "+593 (Ecuador)", 
        "+57 (Colombia)", 
        "+51 (Perú)", 
        "+52 (México)", 
        "+34 (España)", 
        "+1 (Estados Unidos)", 
        "+54 (Argentina)", 
        "+55 (Brasil)", 
        "+56 (Chile)", 
        "Otro"
    ])
    
    celular_cli = col_num.text_input("Número (Sin el código de país)")
    # ==================================
    
    ref_cli = st.text_input("Referencia / Dirección:")
    tipo_veh = st.selectbox("¿Qué necesitas?", ["Taxi 🚖", "Camioneta 🛻", "Ejecutivo 🚔"])
    enviar = st.form_submit_button("🚖 SOLICITAR UNIDAD")

if enviar:
    if not nombre_cli or not ref_cli or not celular_cli:
        st.error("⚠️ Nombre, Teléfono y Referencia son obligatorios.")
    else:
        # FORMATEAR EL NÚMERO DEL CLIENTE PARA WHATSAPP
        tel_final_cli = formatear_internacional(prefijo_pais, celular_cli)
            
        with st.spinner("🔄 Buscando la unidad más cercana..."):
            chof, t_chof, foto_chof = obtener_chofer_mas_cercano(lat_actual, lon_actual)
            id_v = f"TX-{random.randint(1000, 9999)}"
            tipo_solo_texto = tipo_veh.split(" ")[0]
            
            enviar_datos_a_sheets({
                "accion": "registrar_pedido", 
                "cliente": nombre_cli, 
                "telefono_cli": tel_final_cli, 
                "referencia": ref_cli, 
                "conductor": chof if chof else "OCUPADOS", 
                "telefono_chof": t_chof if t_chof else "N/A", 
                "mapa": mapa, 
                "id_viaje": id_v, 
                "tipo": tipo_solo_texto
            })
            
            if chof:
                st.balloons()
                st.markdown(f'<div style="text-align:center; margin-bottom:10px;"><span class="id-badge">🆔 ID: {id_v}</span></div>', unsafe_allow_html=True)
                
                # FOTO
                if foto_chof and "http" in foto_chof:
                    foto_visible = foto_chof.replace("uc?export=view&", "thumbnail?sz=w400&")
                    st.markdown(f"""
                    <div style="display: flex; justify-content: center; margin-bottom: 15px;">
                        <img src="{foto_visible}" style="width: 120px; height: 120px; border-radius: 50%; object-fit: cover; border: 4px solid #25D366; box-shadow: 0 4px 8px rgba(0,0,0,0.2);">
                    </div>""", unsafe_allow_html=True)
                
                st.success(f"✅ ¡Unidad Encontrada! Conductor: **{chof}**")
                
                # BOTÓN WHATSAPP BLINDADO E INTERNACIONAL
                if t_chof and len(t_chof) > 5:
                    msg = f"🚖 *PEDIDO DE {tipo_solo_texto.upper()}*\n🆔 *ID:* {id_v}\n👤 Cliente: {nombre_cli}\n📱 Cel: {tel_final_cli}\n📍 Ref: {ref_cli}\n🗺️ Mapa: {mapa}"
                    link_wa = f"https://api.whatsapp.com/send?phone={t_chof}&text={urllib.parse.quote(msg)}"
                    
                    st.markdown(f"""
                    <a href="{link_wa}" target="_blank" style="background-color: #25D366; color: white; padding: 15px; border-radius: 10px; text-align: center; display: block; text-decoration: none; font-weight: bold; font-size: 20px; margin-top: 10px; box-shadow: 0px 4px 6px rgba(0,0,0,0.1);">
                        📲 ENVIAR UBICACIÓN
                    </a>
                    """, unsafe_allow_html=True)
                else: st.warning("⚠️ El conductor no tiene WhatsApp registrado correctamente.")
            else: st.error("❌ No hay conductores 'LIBRES' cerca de ti en este momento.")

st.markdown("---")
st.markdown(f"""
    <div class="footer">
        <p>¿Necesitas ayuda o quieres reportar algo?</p>
        <p>📧 Contacto: <a href="mailto:{EMAIL_CONTACTO}" target="_self">{EMAIL_CONTACTO}</a></p>
        <p>© 2025 Taxi Seguro Global</p>
    </div>
""", unsafe_allow_html=True)
