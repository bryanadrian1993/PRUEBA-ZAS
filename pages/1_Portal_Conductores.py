import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import urllib.parse
import urllib.request
import base64
import math
import os
import time
import io
import re
from PIL import Image
from datetime import datetime
from streamlit_js_eval import get_geolocation
from streamlit_autorefresh import st_autorefresh
import requests
import streamlit.components.v1 as components

# --- LIBRERIAS NECESARIAS ---
import pytz
from timezonefinder import TimezoneFinder

# --- 🔗 CONFIGURACIÓN TÉCNICA ---
st.set_page_config(page_title="Portal Conductores", page_icon="🚖", layout="centered")

# --- 🔌 CONEXIÓN SEGURA A GOOGLE SHEETS ---
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

try:
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
except Exception as e:
    st.error(f"⚠️ Error de configuración de secretos: {e}")

# --- ⚙️ CONFIGURACIÓN DE NEGOCIO ---
TARIFA_POR_KM = 0.05  # <--- CONFIRMADO: 5 CENTAVOS
DEUDA_MAXIMA = 10.00
LINK_PAYPAL = "https://paypal.me/CAMPOVERDEJARAMILLO"
SHEET_ID = "1l3XXIoAggDd2K9PWnEw-7SDlONbtUvpYVw3UYD_9hus"
URL_SCRIPT = "https://script.google.com/macros/s/AKfycbz-mcv2rnAiT10CUDxnnHA8sQ4XK0qLP7Hj2IhnzKp5xz5ugjP04HnQSN7OMvy4-4Al/exec"

# --- 🛠️ FUNCIONES ---

def obtener_hora_gps(latitud, longitud):
    try:
        if not latitud or not longitud:
            return datetime.now(pytz.timezone('America/Guayaquil')).strftime("%Y-%m-%d %H:%M:%S")
        tf = TimezoneFinder()
        zona_detectada = tf.timezone_at(lng=float(longitud), lat=float(latitud))
        if zona_detectada:
            return datetime.now(pytz.timezone(zona_detectada)).strftime("%Y-%m-%d %H:%M:%S")
        else:
            return datetime.now(pytz.timezone('America/Guayaquil')).strftime("%Y-%m-%d %H:%M:%S")
    except:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def obtener_tarifa_local(lat, lon):
    try:
        # TARIFA BASE (Dólares) = 0.05 (5 centavos)
        tarifa_base_usd = 0.05 

        if not lat or not lon:
            return {"moneda": "USD", "simbolo": "$", "tarifa": tarifa_base_usd, "pais": "Global"}

        tf = TimezoneFinder()
        zona = tf.timezone_at(lng=float(lon), lat=float(lat))
        
        if zona:
            # 🇨🇴 COLOMBIA
            if "Bogota" in zona:
                return {"moneda": "COP", "simbolo": "$", "tarifa": 250.00, "pais": "Colombia"}
            # 🇪🇸 ESPAÑA
            elif "Madrid" in zona or "Ceuta" in zona or "Canary" in zona or "Europe" in zona:
                return {"moneda": "EUR", "simbolo": "€", "tarifa": 0.05, "pais": "España"}
            # 🇲🇽 MÉXICO
            elif "Mexico" in zona:
                return {"moneda": "MXN", "simbolo": "$", "tarifa": 1.00, "pais": "México"}

        # 🇪🇨 ECUADOR / RESTO DEL MUNDO (Dólares)
        return {"moneda": "USD", "simbolo": "$", "tarifa": tarifa_base_usd, "pais": "Ecuador"}
            
    except:
        return {"moneda": "USD", "simbolo": "$", "tarifa": 0.05, "pais": "Ecuador"}

# --- FUNCIÓN DE PAGO PAYPAL ---
def mostrar_boton_pago(monto_deuda):
    st.header("🔓 Desbloqueo Automático (PayPal)")
    st.warning(f"Tu deuda es de **${monto_deuda:.2f}**. Debes pagarla completa para desbloquearte.")
    
    cedula_conductor = st.text_input("Ingresa tu número de identificación:", max_chars=15)
    
    if cedula_conductor:
        client_id = "AbTSfP381kOrNXmRJO8SR7IvjtjLx0Qmj1TyERiV5RzVheYAAxvgGWHJam3KE_iyfcrf56VV_k-MPYmv"
        valor_a_pagar = f"{monto_deuda:.2f}"
        
        _html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                html, body {{ margin: 0; padding: 0; height: 100%; overflow: auto; }}
                #paypal-button-container-final {{ min_height: 600px; width: 100%; }}
            </style>
        </head>
        <body>
            <div id="paypal-button-container-final"></div>
            <script src="https://www.paypal.com/sdk/js?client-id={client_id}&currency=USD&components=buttons"></script>
            <script>
                paypal.Buttons({{
                    style: {{
                        layout: 'vertical',
                        color:  'gold',
                        shape:  'rect',
                        label:  'pay',
                        disableMaxWidth: true 
                    }},
                    createOrder: function(data, actions) {{
                        return actions.order.create({{
                            purchase_units: [{{
                                amount: {{ value: '{valor_a_pagar}' }},
                                custom_id: '{cedula_conductor}'
                            }}]
                        }});
                    }},
                    onApprove: function(data, actions) {{
                        return actions.order.capture().then(function(details) {{
                            alert('¡Pago de ${valor_a_pagar} Exitoso! Tu cuenta se está desbloqueando...');
                        }});
                    }},
                    onError: function (err) {{
                        console.error('Error:', err);
                        alert('No se pudo cargar el formulario de pago.');
                    }}
                }}).render('#paypal-button-container-final');
            </script>
        </body>
        </html>
        """
        st.caption(f"Total a pagar para desbloqueo: ${valor_a_pagar}")
        components.html(_html, height=700, scrolling=True)
    else:
        st.info("👆 Escribe tu identificación para ver el botón de pago.")

def enviar_datos_requests(params):
    try:
        requests.post(URL_SCRIPT, params=params)
    except Exception as e:
        st.error(f"Error de conexión: {e}")

# --- 🔄 INICIALIZAR SESIÓN ---
if 'usuario_activo' not in st.session_state: st.session_state.usuario_activo = False
if 'datos_usuario' not in st.session_state: st.session_state.datos_usuario = {}

# --- 📋 LISTAS ---
PAISES = ["Ecuador", "Colombia", "Perú", "México", "España", "Otro"]
IDIOMAS = ["Español", "English"]
VEHICULOS = ["Taxi 🚖", "Camioneta 🛻", "Ejecutivo 🚔", "Moto Entrega 🏍️"]

# --- 🛰️ CAPTURA GPS ---
loc = get_geolocation()
lat_actual, lon_actual = None, None

if loc and 'coords' in loc:
    lat_actual = loc['coords']['latitude']
    lon_actual = loc['coords']['longitude']

# --- 🛠️ FUNCIONES ---
def reproducir_alerta():
    sound_url = "https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3"
    html_audio = f"""
        <audio autoplay>
        <source src="{sound_url}" type="audio/mp3">
        </audio>
    """
    st.markdown(html_audio, unsafe_allow_html=True)

def cargar_datos(hoja):
    try:
        sh = client.open_by_key(SHEET_ID)
        wks = sh.worksheet(hoja)
        data = wks.get_all_values()
        if not data: return pd.DataFrame()
        headers = data[0]
        rows = data[1:]
        df = pd.DataFrame(rows, columns=headers)
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
    except Exception as e: return f"Error: {e}"

def enviar_datos_a_sheets(datos):
    try:
        params = urllib.parse.urlencode(datos)
        with urllib.request.urlopen(f"{URL_SCRIPT}?{params}") as response:
            return response.read().decode('utf-8')
    except: return "Error"

def actualizar_gps_excel(conductor, lat, lon):
    try:
        sh = client.open_by_key(SHEET_ID)
        try:
            wks = sh.worksheet("UBICACIONES")
        except:
            wks = sh.add_worksheet(title="UBICACIONES", rows=1000, cols=5)
            wks.append_row(["Conductor", "Latitud", "Longitud", "Ultima_Actualizacion"])
        
        conductores = wks.col_values(1)
        nombre_limpio = conductor.strip().upper()
        ahora = obtener_hora_gps(lat, lon)
        
        try:
            fila = conductores.index(nombre_limpio) + 1
            wks.update_cell(fila, 2, lat)
            wks.update_cell(fila, 3, lon)
            wks.update_cell(fila, 4, ahora)
        except ValueError:
            wks.append_row([nombre_limpio, lat, lon, ahora])
        return True
    except: return False

# --- 📱 INTERFAZ ---
st.title("🚖 Portal de Socios")

if st.session_state.usuario_activo:
    # --- PANEL CHOFER ---
    df_fresh = cargar_datos("CHOFERES")
    
    if df_fresh.empty or 'Nombre' not in df_fresh.columns:
        st.error("⚠️ Error de conexión con la base de datos.")
        st.stop()

    user_nom = str(st.session_state.datos_usuario.get('Nombre', '')).strip()
    user_ape = str(st.session_state.datos_usuario.get('Apellido', '')).strip()
    nombre_completo_unificado = f"{user_nom} {user_ape}".upper()
    
    fila_actual = df_fresh[
        (df_fresh['Nombre'].astype(str).str.upper().str.strip() == user_nom.upper()) & 
        (df_fresh['Apellido'].astype(str).str.upper().str.strip() == user_ape.upper())
    ]
    
    st.subheader(f"Bienvenido, {nombre_completo_unificado}")

    foto_actual = st.session_state.datos_usuario.get('Foto_Perfil', 'SIN_FOTO')
    if foto_actual == "SIN_FOTO" and not fila_actual.empty:
        try:
            foto_actual = fila_actual.iloc[0]['Foto_Perfil']
        except: pass

    col_img, col_btn = st.columns([1, 2])
    with col_img:
        if foto_actual and str(foto_actual) != "nan" and len(str(foto_actual)) > 100:
            try:
                img_bytes = base64.b64decode(foto_actual)
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
                with st.spinner("Optimizando..."):
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
                        st.success("✅ ¡Foto guardada!")
                        st.session_state.datos_usuario['Foto_Perfil'] = foto_b64
                        time.sleep(1) 
                        st.rerun()
    st.write("---") 

    gps_activo = st.checkbox("🛰️ ACTIVAR RASTREO GPS", value=True)
    if gps_activo:
        if lat_actual and lon_actual:
            res_gps = actualizar_gps_excel(nombre_completo_unificado, lat_actual, lon_actual)
            if res_gps:
                hora = obtener_hora_gps(lat_actual, lon_actual).split(" ")[1] # Solo mostramos la hora
                st.success(f"📡 SEÑAL EN VIVO ({hora})\n📍 Lat: {lat_actual:.5f}, Lon: {lon_actual:.5f}")
        else:
            st.warning("⏳ Buscando señal satelital... (Asegúrate de permitir la ubicación)")
    else:
        st.info("Rastreo desactivado.")

    if not fila_actual.empty:
        try:
            raw_deuda = str(fila_actual.iloc[0].get('DEUDA', 0)).replace('$','').replace(',','')
            deuda_actual = float(raw_deuda) if raw_deuda else 0.0
        except:
            deuda_actual = 0.0
            
        estado_actual = str(fila_actual.iloc[0].get('Estado', 'OCUPADO'))
        
        if deuda_actual >= DEUDA_MAXIMA and "LIBRE" in estado_actual.upper():
            st.toast("🔒 Deuda detectada: Bloqueando en Excel...", icon="🚫")
            
            try:
                indice_pandas = fila_actual.index[0] 
                fila_excel = indice_pandas + 2
                sh_lock = client.open_by_key(SHEET_ID)
                wks_lock = sh_lock.worksheet("CHOFERES")
                wks_lock.update_cell(fila_excel, 9, "OCUPADO") # La columna 9 es la "I" (Estado)
            except Exception as e:
                st.error(f"Error escribiendo en Excel: {e}")

            estado_actual = "OCUPADO"
        if deuda_actual >= DEUDA_MAXIMA:
            st.error(f"⚠️ TU CUENTA ESTÁ BLOQUEADA. Debes: ${deuda_actual}")
            mostrar_boton_pago(deuda_actual)
        
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("💸 Deuda Actual", f"${deuda_actual:.2f}")
        col_m2.metric("🚦 Estado Actual", estado_actual)

        if deuda_actual > 0:
            st.markdown("---")
            st.subheader("💳 Centro de Pagos")
            st.warning(f"Saldo pendiente: **${deuda_actual:.2f}**")
            
            tab_deuna, tab_paypal = st.tabs(["📲 Pagar con DEUNA", "🌎 Pagar con PAYPAL"])
            
            with tab_deuna:
                st.write("**Escanea el QR:**")
                try:
                    st.image("qr_deuna.png", caption="QR Banco Pichincha", width=250)
                except:
                    st.error("⚠️ No se encontró 'qr_deuna.png' en GitHub")
                msg_wa = f"Hola, soy {nombre_completo_unificado}. Adjunto mi comprobante de pago DEUNA para actualizar mi saldo."
                msg_encoded = urllib.parse.quote(msg_wa)
                numero_whatsapp = "593960643638" 
                st.markdown(f'''
                    <a href="https://wa.me/{numero_whatsapp}?text={msg_encoded}" target="_blank" style="text-decoration:none;">
                        <div style="background-color:#25D366;color:white;padding:12px;text-align:center;border-radius:10px;font-weight:bold;margin-top:10px;">
                            📲 ENVIAR COMPROBANTE AL WHATSAPP
                        </div>
                    </a>
                ''', unsafe_allow_html=True)
            
            with tab_paypal:
                st.subheader("🌎 Pagar con PayPal")
                val_sugerido = float(deuda_actual)
                if val_sugerido < 1.00: 
                    val_sugerido = 1.00
                
                st.write("Confirma o escribe la cantidad a pagar:")
                monto_final = st.number_input("Monto a Pagar ($):", min_value=1.00, value=val_sugerido, step=1.00)
                
                cedula_usuario = str(fila_actual.iloc[0].get('Cedula', '0000000000'))
                client_id = "AbTSfP381kOrNXmRJO8SR7IvjtjLx0Qmj1TyERiV5RzVheYAAxvgGWHJam3KE_iyfcrf56VV_k-MPYmv"
                
                paypal_html_tab = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                    <style>
                        html, body {{ height: 100%; margin: 0; padding: 0; overflow: auto; }}
                        #paypal-button-container-final {{ min_height: 600px; width: 100%; }}
                    </style>
                </head>
                <body>
                    <div id="paypal-button-container-final"></div>
                    <script src="https://www.paypal.com/sdk/js?client-id={client_id}&currency=USD&components=buttons"></script>
                    <script>
                        paypal.Buttons({{
                            style: {{ layout: 'vertical', color: 'gold', shape: 'rect', label: 'pay', disableMaxWidth: true }},
                            createOrder: function(data, actions) {{
                                return actions.order.create({{
                                    purchase_units: [{{ amount: {{ value: '{monto_final}' }}, custom_id: '{cedula_usuario}' }}]
                                }});
                            }},
                            onApprove: function(data, actions) {{
                                return actions.order.capture().then(function(details) {{
                                    alert('✅ Pago exitoso de ${monto_final}.');
                                }});
                            }}
                        }}).render('#paypal-button-container-final');
                    </script>
                </body>
                </html>
                """
                components.html(paypal_html_tab, height=700, scrolling=True)
                
                if deuda_actual >= DEUDA_MAXIMA:
                    st.error(f"⚠️ CUENTA BLOQUEADA (Deuda: ${deuda_actual}).")
                elif deuda_actual > 0:
                    st.warning(f"Tienes deuda pendiente (Límite: ${DEUDA_MAXIMA}).")
                else:
                    st.success("✅ Estás al día.")
        st.divider()

        st.subheader("Gestión de Viaje")
        df_viajes = cargar_datos("VIAJES")
        viaje_activo = pd.DataFrame() 
        
        if not df_viajes.empty and 'Conductor' in df_viajes.columns:
            viaje_activo = df_viajes[
                (df_viajes['Conductor'].astype(str).str.upper() == nombre_completo_unificado) & 
                (df_viajes['Estado'].astype(str) == "EN CURSO")
            ]
            
        if 'ultimo_viaje_avisado' not in st.session_state:
            st.session_state.ultimo_viaje_avisado = ""

        if not viaje_activo.empty:
            datos_v = viaje_activo.iloc[-1]
            id_viaje_actual = f"{datos_v.get('Cliente')}_{datos_v.get('Fecha')}"
            if st.session_state.ultimo_viaje_avisado != id_viaje_actual:
                reproducir_alerta()
                st.toast("🔔 ¡NUEVO VIAJE ASIGNADO!", icon="🚖")
                st.session_state.ultimo_viaje_avisado = id_viaje_actual
        
        if not viaje_activo.empty and "OCUPADO" in estado_actual:
            datos_v = viaje_activo.iloc[-1]
            st.warning("🚖 TIENES UN PASAJERO A BORDO")
            st.write(f"👤 **Cliente:** {datos_v.get('Cliente', 'S/D')}")
            st.write(f"📞 **Tel:** {datos_v.get('Tel Cliente', 'S/D')}")
            st.write(f"📍 **Destino:** {datos_v.get('Referencia', 'S/D')}")
            st.markdown(f"[🗺️ Ver Mapa]({datos_v.get('Mapa', '#')})")
            st.divider()

            if "cobro_realizado" not in st.session_state:
                st.session_state.cobro_realizado = False

            if not st.session_state.cobro_realizado:
                with st.form("form_cobrar_viaje"):
                    st.write("¿Llegaste al destino?")
                    boton_cobrar = st.form_submit_button("🏁 FINALIZAR VIAJE Y COBRAR", type="primary", use_container_width=True)
                
                if boton_cobrar:
                    st.session_state.cobro_realizado = True
                    
                    with st.spinner("⏳ Calculando tarifa según tu país..."):
                        try:
                            # 1. Detectar Configuración Local (Moneda y Precio)
                            config_local = obtener_tarifa_local(lat_actual, lon_actual)
                            tarifa_km = config_local["tarifa"]
                            moneda = config_local["moneda"]
                            simbolo = config_local["simbolo"]
                            pais = config_local["pais"]

                            link_mapa = str(datos_v.get('Mapa', ''))
                            distancia = 2.0
                            
                            try:
                                numeros = re.findall(r'-?\d+\.\d+', link_mapa)
                                if len(numeros) >= 2:
                                    lat_cli = float(numeros[-2])
                                    lon_cli = float(numeros[-1])
                                    
                                    dLat = math.radians(lat_actual - lat_cli)
                                    dLon = math.radians(lon_actual - lon_cli)
                                    a = math.sin(dLat/2)**2 + math.cos(math.radians(lat_cli)) * \
                                        math.cos(math.radians(lat_actual)) * math.sin(dLon/2)**2
                                    c = 2 * math.asin(math.sqrt(a))
                                    distancia = 6371 * c 
                            except: 
                                pass
                            
                            if distancia < 1.0: distancia = 1.0
                            
                            # 2. CÁLCULO DE LA COMISIÓN CON TARIFA LOCAL
                            comision_nueva = round(distancia * tarifa_km, 2)
                            
                            # Enviar a Google Sheets
                            res = enviar_datos_a_sheets({
                                "accion": "finalizar_y_deuda",
                                "conductor": nombre_completo_unificado,
                                "comision": comision_nueva,
                                "km": round(distancia, 2),
                                "moneda": moneda
                            })
                            
                            if res == "Ok" or "Ok" in str(res):
                                st.success(f"✅ ¡VIAJE EN {pais.upper()} FINALIZADO!")
                                st.metric(label="Comisión Generada", value=f"{simbolo} {comision_nueva:.2f} {moneda}")
                                st.balloons()
                                time.sleep(4)
                                st.session_state.cobro_realizado = False
                                st.rerun()
                            else:
                                st.error("❌ Error de conexión.")
                                st.session_state.cobro_realizado = False
                        except Exception as e:
                            st.error(f"❌ Error técnico: {e}")
                            st.session_state.cobro_realizado = False
            
        else:
            if deuda_actual < 10.00:
                st_autorefresh(interval=10000, key="gps_chofer")
            else:
                st.caption("⏸️ GPS en pausa mientras realizas el pago.")

            if deuda_actual >= 10.00:
                st.error(f"🚫 CUENTA BLOQUEADA: Tu deuda (${deuda_actual:.2f}) supera el límite de $10.00")
                st.button("🟢 PONERME LIBRE", disabled=True)
            else:
                if "OCUPADO" in estado_actual:
                    st.info("Estás en estado OCUPADO.")
                
                col_lib, col_ocu = st.columns(2)
            
            with col_lib:
                if st.button("🟢 PONERME LIBRE", use_container_width=True):
                    try:
                        indice_pandas = fila_actual.index[0] 
                        fila_excel = indice_pandas + 2
                        sh_status = client.open_by_key(SHEET_ID)
                        wks_status = sh_status.worksheet("CHOFERES")
                        wks_status.update_cell(fila_excel, 9, "LIBRE")
                        if lat_actual and lon_actual:
                            actualizar_gps_excel(nombre_completo_unificado, lat_actual, lon_actual)
                        st.toast("✅ Estado cambiado a LIBRE", icon="🟢")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error cambiando estado: {e}")
                            
            with col_ocu:
                if st.button("🔴 PONERME OCUPADO", use_container_width=True):
                    try:
                        indice_pandas = fila_actual.index[0] 
                        fila_excel = indice_pandas + 2
                        sh_status = client.open_by_key(SHEET_ID)
                        wks_status = sh_status.worksheet("CHOFERES")
                        wks_status.update_cell(fila_excel, 9, "OCUPADO")
                        st.toast("⏸️ Estado cambiado a OCUPADO", icon="🔴")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error cambiando estado: {e}")
    
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
        else:
            st.write("Cargando datos...")      
    
    if st.button("🔒 CERRAR SESIÓN"):
        st.session_state.usuario_activo = False
        st.rerun()
    st.stop()
else:
    # --- LOGIN / REGISTRO ---
    tab_log, tab_reg = st.tabs(["🔐 INGRESAR", "📝 REGISTRARME"])
    
    with tab_log:
        st.subheader("Acceso Socios")
        l_nom = st.text_input("Nombre registrado")
        l_ape = st.text_input("Apellido registrado")
        l_pass = st.text_input("Contraseña", type="password")
        if st.button("ENTRAR AL PANEL", type="primary"):
            df = cargar_datos("CHOFERES")
            # Validación robusta de columnas
            if df.empty or 'Nombre' not in df.columns:
                st.error("❌ No se pudo conectar con la base de datos 'CHOFERES'. Revisa que la hoja exista y tenga los encabezados correctos.")
            else:
                match = df[
                    (df['Nombre'].astype(str).str.strip().str.upper() == l_nom.strip().upper()) & 
                    (df['Apellido'].astype(str).str.strip().str.upper() == l_ape.strip().upper()) & 
                    (df['Clave'].astype(str).str.strip() == l_pass.strip())
                ]
                if not match.empty:
                    st.session_state.usuario_activo = True
                    st.session_state.datos_usuario = match.iloc[0].to_dict()
                    st.rerun()
                else:
                    st.error("❌ Datos incorrectos o usuario no encontrado.")
    st.markdown("---") 
    with st.expander("¿Olvidaste tu contraseña?"):
        st.info("Ingresa tu correo registrado para recibir tu clave:")
        email_recup = st.text_input("Tu Email", key="email_recup")
        if st.button("📧 Recuperar Clave"):
            if "@" in email_recup:
                with st.spinner("Conectando con el sistema..."):
                    try:
                        resp = requests.post(URL_SCRIPT, params={
                            "accion": "recuperar_clave",
                            "email": email_recup
                        })
                        if "CORREO_ENVIADO" in resp.text:
                            st.success("✅ ¡Enviado! Revisa tu correo.")
                        elif "EMAIL_NO_ENCONTRADO" in resp.text:
                            st.error("❌ Ese correo no está registrado como socio.")
                        else:
                            st.error("Error de conexión.")
                    except:
                        st.error("Error al conectar con el servidor.")
            else:
                st.warning("Escribe un correo válido.")
    
    with tab_reg:
        with st.form("registro_form"):
            st.subheader("Registro de Nuevos Socios")
            col1, col2 = st.columns(2)
            with col1:
                r_nom = st.text_input("Nombres *")
                r_ced = st.text_input("Cédula/ID *")
                r_email = st.text_input("Email *")
                r_pais = st.selectbox("País *", PAISES)
            with col2:
                r_ape = st.text_input("Apellidos *")
                r_telf = st.text_input("WhatsApp (Sin código) *")
                r_veh = st.selectbox("Tipo de Vehículo *", VEHICULOS)
                r_idioma = st.selectbox("Idioma", IDIOMAS)
            r_dir = st.text_input("Dirección *")
            r_pla = st.text_input("Placa *")
            r_pass1 = st.text_input("Contraseña *", type="password")
            
            st.write("---")
            st.write("📷 **Foto de Perfil** (Opcional)")
            archivo_foto_reg = st.file_uploader("Sube tu foto", type=["jpg", "png", "jpeg"])
            
            if st.form_submit_button("✅ COMPLETAR REGISTRO"):
                if r_nom and r_email and r_pass1:
                    foto_para_guardar = "SIN_FOTO"
                    if archivo_foto_reg is not None:
                        try:
                            img = Image.open(archivo_foto_reg).convert('RGB')
                            img = img.resize((150, 150))
                            buffered = io.BytesIO()
                            img.save(buffered, format="JPEG", quality=70)
                            foto_para_guardar = base64.b64encode(buffered.getvalue()).decode()
                        except Exception as e:
                            st.error(f"Error procesando imagen: {e}")

                    try:
                        with st.spinner("Conectando con Excel..."):
                            sh = client.open_by_key(SHEET_ID)
                            wks = sh.worksheet("CHOFERES")
                            # --- SE GUARDA COMO VALIDADO "SI" AUTOMÁTICAMENTE ---
                            # --- USAMOS LA HORA MUNDIAL ---
                            hora_registro = obtener_hora_gps(lat_actual, lon_actual)
                            # ------------------------------

                            nueva_fila = [
                                hora_registro, # A: Fecha (CON HORA MUNDIAL)
                                r_nom, # B: Nombre
                                r_ape, # C: Apellido
                                r_ced, # D: Cedula
                                r_email, # E: Email
                                r_dir, # F: Direccion
                                r_telf, # G: Telefono
                                r_pla, # H: Placa
                                "LIBRE", # I: Estado
                                "", # J: Vence
                                r_pass1, # K: Clave
                                foto_para_guardar, # L: Foto
                                "SI", # M: Validado
                                r_pais, # N: Pais
                                r_idioma, # O: Idioma
                                r_veh, # P: Tipo_Vehiculo
                                0, # Q: KM_ACUMULADOS
                                0.00 # R: DEUDA
                            ]
                            wks.append_row(nueva_fila)
                            st.success("✅ ¡Registro Exitoso! Ya puedes ingresar desde la pestaña superior.")
                            st.balloons()
                            
                    except Exception as e:
                        st.error(f"❌ Error al guardar en Excel: {e}")
                else:
                    st.warning("Por favor, completa los campos obligatorios (*)")

st.markdown('<div style="text-align:center; color:#888; font-size:12px; margin-top:50px;">© 2025 Taxi Seguro Global</div>', unsafe_allow_html=True)
if st.session_state.get('usuario_activo', False):
    datos = st.session_state.get('datos_usuario', {})
    estado_chofer = datos.get('estado', 'OCUPADO')
    if "LIBRE" in str(estado_chofer):
        time.sleep(15) 
        st.rerun()
