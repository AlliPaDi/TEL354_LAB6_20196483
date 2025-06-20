#!/usr/bin/python3

import yaml
import requests
from enum import Enum

# Clases base
class Alumno:
    def __init__(self, nombre, codigo, mac):
        self.nombre = nombre
        self.codigo = codigo
        self.mac = mac

class Curso:
    def __init__(self, codigo, nombre, estado):
        self.codigo = codigo
        self.nombre = nombre
        self.estado = estado
        self.alumnos = []
        self.servidores = []

class Servidor:
    def __init__(self, nombre, ip):
        self.nombre = nombre
        self.ip = ip
        self.servicios = []

class Servicio:
    def __init__(self, nombre, protocolo, puerto):
        self.nombre = nombre
        self.protocolo = protocolo
        self.puerto = puerto

class Conexion:
    def __init__(self, handler, alumno_mac, servidor_ip, servicio):
        self.handler = handler
        self.alumno_mac = alumno_mac
        self.servidor_ip = servidor_ip
        self.servicio = servicio



# Configuración del controlador Floodlight
FL_CONTROLLER_IP = "10.20.12.228" 
FL_CONTROLLER_PORT = "8080"
FL_BASE_URL = f"http://{FL_CONTROLLER_IP}:{FL_CONTROLLER_PORT}/wm"

def get_attachment_point(mac):
    """Se obtiene el switch y puerto donde está conectado un host por su MAC"""
    url = f"{FL_BASE_URL}/device/"
    try:
        response = requests.get(url)
        response.raise_for_status() 
        
        devices = response.json()
        for device in devices:
            if device.get('mac') and device['mac'][0] == mac:
                if device.get('attachmentPoint'):
                     # Obtener el primer punto de conexión del host
                    attachment_point = device['attachmentPoint'][0]
                    switch_dpid = attachment_point.get('switchDPID')
                    port = attachment_point.get('port')
                    return switch_dpid, port
                
    except requests.exceptions.RequestException as e:
        print(f"Ocurrió un error al obtener los puntos de conexión: {e}")

    return None, None

def get_attachment_point_by_ip(host_ip):
    """Se obtiene el switch y puerto donde está conectado un host por su IP"""
    url = f"{FL_BASE_URL}/device/"
    try:
        response = requests.get(url)
        response.raise_for_status() 
        
        devices = response.json()
        for device in devices:
            # Buscar por IP en lugar de MAC
            if device.get('ipv4') and len(device['ipv4']) > 0:
                if device['ipv4'][0] == host_ip:
                    if device.get('attachmentPoint'):
                        # Obtener el primer punto de conexión del host
                        attachment_point = device['attachmentPoint'][0]
                        switch_dpid = attachment_point.get('switchDPID')
                        port = attachment_point.get('port')
                        return switch_dpid, port
                
    except requests.exceptions.RequestException as e:
        print(f"Ocurrió un error al obtener los puntos de conexión por IP: {e}")

    return None, None

def get_route(src_switch, dst_switch):
    """Obtiene la ruta entre dos switches"""
    url = f"{FL_BASE_URL}/path/{src_switch}/{dst_switch}/json"
    try:
        response = requests.get(url)
        return response.json().get('path', [])
    except Exception as e:
        print(f"Error al obtener ruta: {e}")
        return []

def build_route(conexion, alumnos, cursos, servidores):
    """Crea los flows necesarios para una conexión"""
    # Validar autorización
    alumno = next((a for a in alumnos if a.mac == conexion.alumno_mac), None)
    if not alumno:
        print("Alumno no encontrado")
        return False
    
    # Buscar servidor
    servidor = next((s for s in servidores if s.ip == conexion.servidor_ip), None)
    if not servidor:
        print("Servidor no encontrado")
        return False
    
    # Verificar si el alumno tiene acceso al servicio
    autorizado = False
    for curso in cursos:
        if curso.estado == "DICTANDO" and alumno.codigo in curso.alumnos:
            for srv in curso.servidores:
                # srv es un diccionario, no un objeto
                if srv['nombre'] == servidor.nombre:
                    # Acceder a servicios_permitidos como clave del diccionario
                    servicios_permitidos = srv.get('servicios_permitidos', [])
                    for servicio_permitido in servicios_permitidos:
                        if servicio_permitido == conexion.servicio.nombre:
                            autorizado = True
                            break
                    if autorizado:
                        break
            if autorizado:
                break
    
    if not autorizado:
        print("Alumno no autorizado para este servicio")
        return False
    
    # Obtener puntos de conexión
    src_switch, src_port = get_attachment_point(conexion.alumno_mac)
    dst_switch, dst_port = get_attachment_point_by_ip(servidor.ip) 
       
    if not src_switch or not dst_switch:
        print("No se pudo determinar la ubicación de los hosts")
        return False
    
    # Obtener ruta
    ruta = get_route(src_switch, dst_switch)
    if not ruta:
        print("No se encontró ruta entre los hosts")
        return False
    
    # Crear flows
    print(f"Creando flows para la conexión {conexion.handler}")
    print(f"Ruta encontrada: {ruta}")
    print(f"Alumno: {alumno.nombre} ({conexion.alumno_mac})")
    print(f"Servidor: {servidor.nombre} ({servidor.ip})")
    print(f"Servicio: {conexion.servicio.nombre} ({conexion.servicio.protocolo}:{conexion.servicio.puerto})")
   
   

    
    return True

# Variables globales
alumnos = []
cursos = []
servidores = []
conexiones = []

def menu_principal():
    while True:
        print("\n############################################")
        print("Network Policy manager de La UPSM")
        print("############################################\n")
        print("Seleccione una opción:")
        print("1) Importar")
        print("2) Exportar")
        print("3) Cursos")
        print("4) Alumnos")
        print("5) Servidores")
        print("6) Políticas")
        print("7) Conexiones")
        print("8) Salir")
        
        opcion = input(">>> ")
        
        if opcion == "1":
            importar()
        elif opcion == "2":
            exportar()
        elif opcion == "3":
            menu_cursos()
        elif opcion == "4":
            menu_alumnos()
        elif opcion == "5":
            menu_servidores()
        elif opcion == "6":
            menu_politicas()
        elif opcion == "7":
            menu_conexiones()
        elif opcion == "8":
            break
        else:
            print("Opción no válida")

def importar():
    filename = input("Nombre del archivo a importar: ")
    try:
        with open(filename, 'r') as file:
            data = yaml.safe_load(file)
            
            # Importar alumnos
            alumnos.clear()
            for alumno_data in data.get('alumnos', []):
                alumnos.append(Alumno(
                    alumno_data['nombre'],
                    alumno_data['codigo'],
                    alumno_data['mac']
                ))
            
            # Importar cursos
            cursos.clear()
            for curso_data in data.get('cursos', []):
                curso = Curso(
                    curso_data['codigo'],
                    curso_data['nombre'],
                    curso_data['estado']
                )
                curso.alumnos = curso_data.get('alumnos', [])
                curso.servidores = curso_data.get('servidores', [])
                cursos.append(curso)
            
            # Importar servidores
            servidores.clear()
            for servidor_data in data.get('servidores', []):
                servidor = Servidor(
                    servidor_data['nombre'],
                    servidor_data['ip']
                )
                servidor.servicios = [Servicio(s['nombre'], s['protocolo'], s['puerto']) 
                                  for s in servidor_data.get('servicios', [])]
                servidores.append(servidor)
            
            print("Datos importados correctamente")
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo '{filename}'")
    except yaml.YAMLError as e:
        print(f"Error en el formato YAML: {e}")
    except Exception as e:
        print(f"Error inesperado: {str(e)}")

def exportar():
    filename = input("Nombre del archivo a exportar: ")
    try:
        data = {
            'alumnos': [{'nombre': a.nombre, 'codigo': a.codigo, 'mac': a.mac} for a in alumnos],
            'cursos': [{
                'codigo': c.codigo,
                'nombre': c.nombre,
                'estado': c.estado,
                'alumnos': c.alumnos,
                'servidores': c.servidores
            } for c in cursos],
            'servidores': [{
                'nombre': s.nombre,
                'ip': s.ip,
                'servicios': [{
                    'nombre': sv.nombre,
                    'protocolo': sv.protocolo,
                    'puerto': sv.puerto
                } for sv in s.servicios]
            } for s in servidores]
        }
        
        with open(filename, 'w') as file:
            yaml.dump(data, file)
        
        print("Datos exportados correctamente")
    except Exception as e:
        print(f"Error al exportar: {e}")

def menu_cursos():
    while True:
        print("\nMenú Cursos:")
        print("1) Listar cursos")
        print("2) Mostrar detalle de un curso")
        print("3) Actualizar alumnos (Agregar/Eliminar)")
        print("4) Volver")
        
        opcion = input(">>> ").strip()
        
        if opcion == "1":
            listar_cursos()
        elif opcion == "2":
            mostrar_detalle_curso()
        elif opcion == "3":
            actualizar_alumnos_curso()
        elif opcion == "4":
            break
        else:
            print("Opción no válida. Intente nuevamente.")

def listar_cursos():
    print("\n=== LISTA DE CURSOS ===")
    if not cursos:
        print("No hay cursos registrados.")
        return
    
    for curso in cursos:
        print(f"\n- Código: {curso.codigo}")
        print(f"  Nombre: {curso.nombre}")
        print(f"  Estado: {curso.estado}")
        print(f"  Alumnos matriculados: {len(curso.alumnos)}")

def mostrar_detalle_curso():
    codigo = input("\nIngrese el código del curso (ej. TEL354): ").strip().upper()
    curso = next((c for c in cursos if c.codigo == codigo), None)
    
    if not curso:
        print(f"Error: No existe un curso con código {codigo}.")
        return
    
    print(f"\n=== DETALLE DEL CURSO: {curso.codigo} ===")
    print(f"Nombre: {curso.nombre}")
    print(f"Estado: {curso.estado}")
    
    # Lista de alumnos matriculados
    print("\nAlumnos matriculados:")
    if not curso.alumnos:
        print("  No hay alumnos registrados.")
    else:
        for codigo_alumno in curso.alumnos:
            alumno = next((a for a in alumnos if a.codigo == codigo_alumno), None)
            if alumno:
                print(f"  - {alumno.nombre} (Código: {alumno.codigo}, MAC: {alumno.mac})")
    
    # Servidores y servicios permitidos
    print("\nServidores asociados:")
    if not curso.servidores:
        print("  No hay servidores configurados.")
    else:
        for servidor in curso.servidores:
            print(f"  - {servidor['nombre']}")
            if 'servicios_permitidos' in servidor:
                print("    Servicios permitidos:", ", ".join(servidor['servicios_permitidos']))        

def actualizar_alumnos_curso():
    codigo_curso = input("\nIngrese el código del curso (ej. TEL354): ").strip().upper()
    curso = next((c for c in cursos if c.codigo == codigo_curso), None)
    
    if not curso:
        print(f"Error: No existe un curso con código {codigo_curso}.")
        return
    
    print(f"\nCurso seleccionado: {curso.nombre} ({curso.codigo})")
    
    while True:
        print("\n1) Agregar alumno")
        print("2) Eliminar alumno")
        print("3) Volver")
        
        opcion = input(">>> ").strip()
        
        if opcion == "1":
            # Agregar alumno (ej. Oscar Wilde)
            print("\nAlumnos disponibles para agregar:")
            alumnos_no_matriculados = [a for a in alumnos if a.codigo not in curso.alumnos]
            
            if not alumnos_no_matriculados:
                print("No hay alumnos disponibles para agregar.")
                continue
            
            for i, alumno in enumerate(alumnos_no_matriculados, 1):
                print(f"{i}. {alumno.nombre} (Código: {alumno.codigo})")
            
            try:
                seleccion = int(input("Seleccione el alumno a agregar (número): ")) - 1
                if seleccion < 0 or seleccion >= len(alumnos_no_matriculados):
                    print("Selección inválida.")
                    continue
                
                alumno = alumnos_no_matriculados[seleccion]
                curso.alumnos.append(alumno.codigo)
                print(f"\nAlumno '{alumno.nombre}' agregado al curso {curso.codigo}.")
            except ValueError:
                print("Error: Ingrese un número válido.")
        
        elif opcion == "2":
            # Eliminar alumno
            if not curso.alumnos:
                print("No hay alumnos matriculados para eliminar.")
                continue
            
            print("\nAlumnos matriculados:")
            for i, codigo_alumno in enumerate(curso.alumnos, 1):
                alumno = next((a for a in alumnos if a.codigo == codigo_alumno), None)
                if alumno:
                    print(f"{i}. {alumno.nombre} (Código: {alumno.codigo})")
            
            try:
                seleccion = int(input("Seleccione el alumno a eliminar (número): ")) - 1
                if seleccion < 0 or seleccion >= len(curso.alumnos):
                    print("Selección inválida.")
                    continue
                
                alumno_eliminado = curso.alumnos.pop(seleccion)
                print(f"\nAlumno con código '{alumno_eliminado}' eliminado del curso.")
            except ValueError:
                print("Error: Ingrese un número válido.")
        
        elif opcion == "3":
            break
        
        else:
            print("Opción no válida.")    
        
def menu_alumnos():
    while True:
        print("\nMenú Alumnos:")
        print("1) Listar todos los alumnos")
        print("2) Listar alumnos por curso")
        print("3) Mostrar detalle")
        print("4) Crear")
        print("5) Actualizar")
        print("6) Borrar")
        print("7) Volver")
        
        opcion = input(">>> ")
        
        if opcion == "1":
            listar_alumnos()
        elif opcion == "2":
            codigo_curso = input("Ingrese el código del curso (ej. TEL354): ").strip().upper()
            listar_alumnos(filtro_curso=codigo_curso)
        elif opcion == "3":
            mostrar_detalle_alumno()
        elif opcion == "4":
            crear_alumno()
        elif opcion == "5":
            actualizar_alumno()
        elif opcion == "6":
            borrar_alumno()
        elif opcion == "7":
            break
        else:
            print("Opción no válida")

def listar_alumnos(filtro_curso=None):

    print("\n=== LISTA DE ALUMNOS ===")
    
    alumnos_filtrados = []
    
    if filtro_curso:
        # Buscar el curso primero
        curso = next((c for c in cursos if c.codigo == filtro_curso), None)
        if not curso:
            print(f"No se encontró el curso {filtro_curso}")
            return
        
        # Filtrar alumnos matriculados en este curso
        alumnos_filtrados = [a for a in alumnos if a.codigo in curso.alumnos]
        print(f"Alumnos matriculados en {curso.codigo} - {curso.nombre}:")
    else:
        alumnos_filtrados = alumnos
        print("Todos los alumnos registrados:")
    
    if not alumnos_filtrados:
        print("No se encontraron alumnos" + (" para este filtro" if filtro_curso else ""))
        return
    
    for i, alumno in enumerate(alumnos_filtrados, 1):
        # Obtener cursos del alumno para mostrar adicionalmente
        cursos_alumno = [c.codigo for c in cursos if alumno.codigo in c.alumnos]
        print(f"{i}. {alumno.nombre} ({alumno.codigo}) - MAC: {alumno.mac}")

def mostrar_detalle_alumno():
    codigo_buscado = input("Ingrese código del alumno: ").strip() 
    
    alumno = None
    for a in alumnos:
        if str(a.codigo).strip() == codigo_buscado:
            alumno = a
            break
    
    if not alumno:
        print(f"\n¡Error! No se encontró alumno con código {codigo_buscado}")
        return
    
    print("\n=== DETALLE COMPLETO DEL ALUMNO ===")
    print(f"Nombre completo: {alumno.nombre}")
    print(f"Código: {alumno.codigo}")
    print(f"Dirección MAC: {alumno.mac}")
    
    # Cursos matriculados con más detalles
    cursos_matriculados = [c for c in cursos if str(alumno.codigo) in [str(cod) for cod in c.alumnos]]
    
    if not cursos_matriculados:
        print("\nEl alumno no está matriculado en ningún curso actualmente")
    else:
        print("\nMATRÍCULAS ACTIVAS:")
        for curso in cursos_matriculados:
            print(f"\n• {curso.codigo}: {curso.nombre}")
            print(f"  Estado: {curso.estado}")
            
            if curso.servidores:
                print("  Servidores accesibles:")
                for servidor in curso.servidores:
                    srv = next((s for s in servidores if s.nombre == servidor['nombre']), None)
                    if srv:
                        print(f"  - {srv.nombre} (IP: {srv.ip})")
                        if 'servicios_permitidos' in servidor:
                            print("    Servicios permitidos:", ", ".join(servidor['servicios_permitidos']))

def crear_alumno():
    nombre = input("Nombre: ")
    codigo = input("Código: ")
    mac = input("MAC: ")
    
    if any(a.codigo == codigo for a in alumnos):
        print("Ya existe un alumno con ese código")
        return
    
    alumnos.append(Alumno(nombre, codigo, mac))
    print("Alumno creado exitosamente")

def menu_servidores():
    while True:
        print("\nMenú Servidores:")
        print("1) Crear")
        print("2) Listar")
        print("3) Mostrar detalle")
        print("4) Actualizar")
        print("5) Borrar")
        print("6) Volver")
        
        opcion = input(">>> ")
        
        if opcion == "1":
            crear_servidor()
        elif opcion == "2":
            listar_servidores()
        elif opcion == "3":
            nombre = input("Ingrese el nombre del servidor (ej. 'Servidor 1'): ").strip()
            mostrar_detalle_servidor(nombre)
        elif opcion == "4":
            actualizar_servidor()
        elif opcion == "5":
            borrar_servidor()
        elif opcion == "6":
            break
        else:
            print("Opción no válida")

def listar_servidores():
    """Lista todos los servidores registrados"""
    print("\n=== LISTA DE SERVIDORES ===")
    if not servidores:
        print("No hay servidores registrados")
        return
    
    for i, servidor in enumerate(servidores, 1):
        print(f"{i}. {servidor.nombre} (IP: {servidor.ip})")

def mostrar_detalle_servidor(nombre_servidor):
    servidor = next((s for s in servidores if s.nombre.lower() == nombre_servidor.lower()), None)
    
    if not servidor:
        print(f"\nError: No se encontró el servidor '{nombre_servidor}'")
        return
    
    print(f"\n=== DETALLES DEL SERVIDOR: {servidor.nombre.upper()} ===")
    print(f"Dirección IP: {servidor.ip}")
    print("Servicios ofrecidos:")
    
    if not servidor.servicios:
        print(" - Este servidor no tiene servicios registrados")
    else:
        for servicio in servidor.servicios:
            print(f" - {servicio.nombre}: {servicio.protocolo}/{servicio.puerto}")
    
    
    # Verificación automática para Servidor 1
    if servidor.nombre.lower() == "servidor 1":
        ip_vm_h3 = "10.0.0.3"  
        
        print("\n--- VERIFICACIÓN DE IP CON VM H3 ---")
        print(f"IP configurada para VM H3 en la topología: {ip_vm_h3}")
        
        if servidor.ip == ip_vm_h3:
            print("Las direcciones IP coinciden")
        else:
            print("Las direcciones IP NO coinciden")
            print("Nota: La IP del servidor debería coincidir con la IP asignada a la VM H3")

def menu_politicas():
    while True:
        print("\nMenú Políticas:")
        print("1) Listar cursos con acceso a un servicio")  # Nueva opción
        print("2) Volver")
        
        opcion = input(">>> ")
        
        if opcion == "1":
            listar_cursos_con_acceso_servicio()  # Nueva función
        elif opcion == "2":
            break
        else:
            print("Opción no válida")

def listar_cursos_con_acceso_servicio():
    # Mostrar servidores disponibles para selección
    print("\nServidores registrados:")
    for i, servidor in enumerate(servidores, 1):
        print(f"{i}. {servidor.nombre} (IP: {servidor.ip})")
    
    try:
        servidor_idx = int(input("\nSeleccione el servidor (número): ")) - 1
        if servidor_idx < 0 or servidor_idx >= len(servidores):
            print("Error: Selección inválida")
            return
    except ValueError:
        print("Error: Ingrese un número válido")
        return

    servidor = servidores[servidor_idx]

    # Mostrar servicios disponibles en el servidor seleccionado
    print(f"\nServicios disponibles en {servidor.nombre}:")
    for i, servicio in enumerate(servidor.servicios, 1):
        print(f"{i}. {servicio.nombre} ({servicio.protocolo}:{servicio.puerto})")
    
    try:
        servicio_idx = int(input("\nSeleccione el servicio (número): ")) - 1
        if servicio_idx < 0 or servicio_idx >= len(servidor.servicios):
            print("Error: Selección inválida")
            return
    except ValueError:
        print("Error: Ingrese un número válido")
        return

    servicio = servidor.servicios[servicio_idx]

    # Filtrar cursos con acceso al servicio seleccionado
    cursos_con_acceso = []
    for curso in cursos:
        if curso.estado != "DICTANDO":
            continue  # Solo cursos activos
        
        for srv_curso in curso.servidores:
            if srv_curso['nombre'] == servidor.nombre:
                if 'servicios_permitidos' in srv_curso and servicio.nombre in srv_curso['servicios_permitidos']:
                    cursos_con_acceso.append(curso)
                    break

    # Mostrar resultados
    print(f"\n=== CURSOS CON ACCESO A '{servicio.nombre.upper()}' EN {servidor.nombre.upper()} ===")
    if not cursos_con_acceso:
        print("No hay cursos activos con acceso a este servicio.")
    else:
        for curso in cursos_con_acceso:
            print(f"- {curso.codigo}: {curso.nombre} (Estado: {curso.estado})")
            
def menu_conexiones():
    while True:
        print("\nMenú Conexiones:")
        print("1) Crear")
        print("2) Listar")
        print("3) Mostrar detalle")
        print("4) Recalcular")
        print("5) Actualizar")
        print("6) Borrar")
        print("7) Volver")
        
        opcion = input(">>> ")
        
        if opcion == "1":
            crear_conexion()
        elif opcion == "2":
            listar_conexiones()
        elif opcion == "3":
            mostrar_detalle_conexion()
        elif opcion == "4":
            recalcular_conexion()
        elif opcion == "5":
            actualizar_conexion()
        elif opcion == "6":
            borrar_conexion()
        elif opcion == "7":
            break
        else:
            print("Opción no válida")

def crear_conexion():
    print("\nCrear nueva conexión")
    
    # Mostrar alumnos
    print("\nAlumnos disponibles:")
    for i, alumno in enumerate(alumnos, 1):
        print(f"{i}. {alumno.nombre} ({alumno.mac})")
    
    alumno_idx = int(input("Seleccione alumno (número): ")) - 1
    if alumno_idx < 0 or alumno_idx >= len(alumnos):
        print("Selección inválida")
        return
    
    # Mostrar servidores
    print("\nServidores disponibles:")
    for i, servidor in enumerate(servidores, 1):
        print(f"{i}. {servidor.nombre} ({servidor.ip})")
    
    servidor_idx = int(input("Seleccione servidor (número): ")) - 1
    if servidor_idx < 0 or servidor_idx >= len(servidores):
        print("Selección inválida")
        return
    
    # Mostrar servicios del servidor seleccionado
    servidor = servidores[servidor_idx]
    print(f"\nServicios disponibles en {servidor.nombre}:")
    for i, servicio in enumerate(servidor.servicios, 1):
        print(f"{i}. {servicio.nombre} ({servicio.protocolo}:{servicio.puerto})")
    
    servicio_idx = int(input("Seleccione servicio (número): ")) - 1
    if servicio_idx < 0 or servicio_idx >= len(servidor.servicios):
        print("Selección inválida")
        return
    
    servicio = servidor.servicios[servicio_idx]
    
    # Crear conexión
    handler = f"conn_{len(conexiones)+1}"
    conexion = Conexion(handler, alumnos[alumno_idx].mac, servidor.ip, servicio)
    
    if build_route(conexion, alumnos, cursos, servidores):
        conexiones.append(conexion)
        print(f"Conexión creada exitosamente. Handler: {handler}")
    else:
        print("No se pudo crear la conexión")

def listar_conexiones():
    print("\nLista de conexiones activas:")
    for conexion in conexiones:
        alumno = next((a for a in alumnos if a.mac == conexion.alumno_mac), None)
        servidor = next((s for s in servidores if s.ip == conexion.servidor_ip), None)
        
        print(f"Handler: {conexion.handler}")
        print(f"Alumno: {alumno.nombre if alumno else 'Desconocido'}")
        print(f"Servidor: {servidor.nombre if servidor else 'Desconocido'}")
        print(f"Servicio: {conexion.servicio.nombre} ({conexion.servicio.protocolo}:{conexion.servicio.puerto})")
        print("-" * 30)

def borrar_conexion():
    handler = input("Ingrese el handler de la conexión a borrar: ")
    conexion = next((c for c in conexiones if c.handler == handler), None)
    
    if not conexion:
        print("Conexión no encontrada")
        return
    
    # eliminar los flows del switch
    print(f"Eliminando flows para la conexión {handler}...")
    
    conexiones.remove(conexion)
    print("Conexión eliminada exitosamente")

def main():
    menu_principal()

if __name__ == "__main__":
    main()