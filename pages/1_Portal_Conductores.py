import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import numpy as np
import math
from streamlit_js_eval import get_geolocation
import time
import urllib.parse
import urllib.request
import requests # <--- ¡ESTA LÍNEA FALTABA!

# --- 🔗 CONFIGURACIÓN ---
st.set_page_config(page_title="Pedir Taxi", page_icon="🙋‍♂️", layout="centered")

# --- 🔌 CONEXIÓN GOOGLE SHEETS ---
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
try:
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
except:
    st.error("⚠️ Error de credenciales.")
    st.stop()

SHEET_ID = "1l3XXIoAggDd2K9PWnEw-7SDlONbtUvpYVw3UYD_9hus"
URL_SCRIPT = "https://script.google.com/macros/s/AKfycbz-mcv2rnAiT10CUDxnnHA8sQ4XK0qLP7Hj2IhnzKp5xz5ugjP04HnQSN7OMvy4-4Al/exec"

# --- 📍 OBTENER UBICACIÓN CLIENTE ---
loc = get_geolocation()
lat_cliente, lon_cliente = None, None

if loc and 'coords' in loc:
    lat_cliente = loc['coords']['latitude']
    lon_cliente = loc['coords']['longitude']
else:
    # SI NO HAY GPS, USAMOS UNA UBICACIÓN POR DEFECTO PARA QUE NO FALLE LA PRUEBA
    st.warning("⚠️ No detecto tu GPS. Usando ubicación de prueba (El Coca).")
    lat_cliente = -0.7265 
    lon_cliente = -76.8705

# --- 🧮 FUNCIÓN DISTANCIA (Haversine) ---
def calcular_distancia(lat1, lon1, lat2, lon2):
    R = 6371 # Radio tierra km
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c

# --- 📥 CARGAR DATOS ---
def obtener_conductores_activos():
    try:
        sh = client.open_by_key(SHEET_ID)
        
        # 1. Traer datos de CHOFERES
        ws_choferes = sh.worksheet("CHOFERES")
        df_choferes = pd.DataFrame(ws_choferes.get_all_records())
        
        # 2. Traer datos de UBICACIONES
        ws_ubi = sh.worksheet("UBICACIONES")
        data_ubi = ws_ubi.get_all_values()
        if not data_ubi: return []
        df_ubi = pd.DataFrame(data_ubi[1:], columns=data_ubi[0]) 
        
        # 3. Limpieza
        df_choferes.columns = df_choferes.columns.str.strip()
        df_ubi.columns = df_ubi.columns.str.strip()

        # 4. Unir tablas
        df_choferes['Nombre_Completo'] = (df_choferes['Nombre'].astype(str) + " " + df_choferes['Apellido'].astype(str)).str.strip().str.upper()
        df_ubi['Conductor'] = df_ubi['Conductor'].astype(str).str.strip().str.upper()
        
        # Merge
        df_final = pd.merge(df_choferes, df_ubi, left_on='Nombre_Completo', right_on='Conductor', how='inner')
        
        return df_final
    except Exception as e:
        st.error(f"Error base de datos: {e}")
        return pd.DataFrame()

# --- 📱 INTERFAZ ---
st.title("🙋‍♂️ Pedir Taxi (Modo Prueba)")

if lat_cliente:
    st.success(f"📍 Tu ubicación detectada: {lat_cliente:.4f}, {lon_cliente:.4f}")
    
    with st.form("form_pedido"):
        nombre = st.text_input("Tu Nombre")
        whatsapp = st.text_input("WhatsApp (Sin código)")
        referencia = st.text_input("Referencia / Dirección")
        
        # BUSCAR CONDUCTORES
        df_activos = obtener_conductores_activos()
        conductores_cerca = []
        
        if not df_activos.empty:
            for index, row in df_activos.iterrows():
                estado = str(row.get('Estado', '')).upper()
                validado = str(row.get('Validado', '')).upper()
                
                if "LIBRE" in estado and "SI" in validado:
                    try:
                        lat_cond = float(row['Latitud'])
                        lon_cond = float(row['Longitud'])
                        dist = calcular_distancia(lat_cliente, lon_cliente, lat_cond, lon_cond)
                        
                        # RADIO GIGANTE PARA PRUEBAS (10,000 KM)
                        if dist <= 10000: 
                            conductores_cerca.append({
                                "nombre": row['Nombre_Completo'],
                                "auto": row.get('Tipo_Vehiculo', 'Taxi'),
                                "placa": row.get('Placa', '---'),
                                "distancia": dist,
                                "tel_conductor": row.get('Telefono', '')
                            })
                    except: pass
        
        conductores_cerca.sort(key=lambda x: x['distancia'])
        
        if conductores_cerca:
            st.info(f"✅ Se encontraron {len(conductores_cerca)} conductores disponibles.")
            
            opciones = [f"{c['nombre']} ({c['auto']} - {c['placa']}) a {c['distancia']:.1f} km" for c in conductores_cerca]
            seleccion = st.selectbox("Elige tu conductor:", options=opciones)
            
            enviar = st.form_submit_button("🚖 SOLICITAR UNIDAD")
            
            if enviar:
                if nombre and whatsapp and referencia:
                    index_sel = opciones.index(seleccion)
                    chofer_elegido = conductores_cerca[index_sel]
                    
                    link_mapa = f"https://www.google.com/maps/search/?api=1&query={lat_cliente},{lon_cliente}"
                    
                    try:
                        params = {
                            "accion": "registrar_pedido",
                            "id_viaje": str(int(time.time())),
                            "cliente": nombre,
                            "tel_cliente": whatsapp,
                            "referencia": referencia,
                            "conductor": chofer_elegido['nombre'],
                            "tel_conductor": chofer_elegido['tel_conductor'],
                            "mapa": link_mapa
                        }
                        # AQUÍ USAMOS REQUESTS QUE YA ESTÁ IMPORTADO
                        requests.post(URL_SCRIPT, params=params)
                        
                        requests.post(URL_SCRIPT, params={
                            "accion": "cambiar_estado",
                            "conductor": chofer_elegido['nombre'],
                            "estado": "OCUPADO"
                        })
                        
                        st.balloons()
                        st.success(f"✅ ¡Taxi Solicitado! {chofer_elegido['nombre']} va en camino.")
                        st.info("Por favor espera a que el conductor te contacte.")
                        
                    except Exception as e:
                        st.error(f"Error de conexión: {e}")
                else:
                    st.error("Por favor llena todos los campos.")
        else:
            st.warning("⚠️ No hay conductores conectados con estado 'LIBRE'.")
            st.form_submit_button("Actualizar búsqueda")

else:
    st.info("Esperando señal GPS...")
