import os
import json
import sys
import traceback

try:
    import live2d.v3 as live2d
    import resources
except ImportError as e:
    print(f"Error importando módulos: {e}")
    sys.exit(1)


def check_model_files():
    """Verificar archivos del modelo Live2D"""
    print("=== VERIFICACIÓN DE ARCHIVOS DEL MODELO ===")
    
    try:
        # Ruta base del modelo
        model_dir = os.path.join(resources.RESOURCES_DIRECTORY, "holograma_women")
        model_json = os.path.join(model_dir, "holograma_women.model3.json")
        
        print(f"Directorio del modelo: {model_dir}")
        print(f"Archivo JSON: {model_json}")
        
        
        if not os.path.exists(model_dir):
            print("❌ Directorio del modelo no existe")
            return False
        
        if not os.path.exists(model_json):
            print("❌ Archivo .model3.json no existe")
            return False
        
        # Leer y verificar el archivo JSON
        print("\n--- Contenido del modelo JSON ---")
        with open(model_json, 'r', encoding='utf-8') as f:
            model_data = json.load(f)
        
        print(f"Versión: {model_data.get('Version', 'No especificada')}")
        
        # Verificar archivos referenciados
        required_files = []
        
        # Archivo .moc3
        if 'FileReferences' in model_data and 'Moc' in model_data['FileReferences']:
            moc_file = model_data['FileReferences']['Moc']
            required_files.append(('MOC3', moc_file))
        
        # Texturas
        if 'FileReferences' in model_data and 'Textures' in model_data['FileReferences']:
            for i, texture in enumerate(model_data['FileReferences']['Textures']):
                required_files.append((f'Texture {i}', texture))
        
        # Física (opcional)
        if 'FileReferences' in model_data and 'Physics' in model_data['FileReferences']:
            physics_file = model_data['FileReferences']['Physics']
            required_files.append(('Physics', physics_file))
        
        # Pose (opcional)
        if 'FileReferences' in model_data and 'Pose' in model_data['FileReferences']:
            pose_file = model_data['FileReferences']['Pose']
            required_files.append(('Pose', pose_file))
        
        print(f"\n--- Verificando {len(required_files)} archivos referenciados ---")
        all_files_exist = True
        
        for file_type, filename in required_files:
            file_path = os.path.join(model_dir, filename)
            exists = os.path.exists(file_path)
            status = "✓" if exists else "❌"
            size = f"({os.path.getsize(file_path)} bytes)" if exists else ""
            
            print(f"{status} {file_type}: {filename} {size}")
            
            if not exists:
                all_files_exist = False
        
        # Mostrar todos los archivos en el directorio
        print(f"\n--- Todos los archivos en {model_dir} ---")
        try:
            files = os.listdir(model_dir)
            for file in sorted(files):
                file_path = os.path.join(model_dir, file)
                if os.path.isfile(file_path):
                    size = os.path.getsize(file_path)
                    print(f"  {file} ({size} bytes)")
        except Exception as e:
            print(f"Error listando archivos: {e}")
        
        return all_files_exist
        
    except Exception as e:
        print(f"Error verificando archivos: {e}")
        traceback.print_exc()
        return False


def test_model_loading():
    """Probar carga del modelo Live2D paso a paso"""
    print("\n=== PRUEBA DE CARGA DEL MODELO ===")
    
    try:
        # Inicializar Live2D
        print("1. Inicializando Live2D Framework...")
        live2d.init()
        print("✓ Framework inicializado")
        
        # Crear modelo
        print("2. Creando instancia del modelo...")
        model = live2d.LAppModel()
        print("✓ Modelo creado")
        
        # Intentar cargar
        model_path = os.path.join(
            resources.RESOURCES_DIRECTORY, 
            "holograma_men", 
            "holograma_men.model3.json"
        )
        
        print(f"3. Cargando modelo desde: {model_path}")
        
        # Método de carga con más debug
        try:
            success = model.LoadModelJson(model_path)
            print(f"   LoadModelJson retornó: {success}")
            
            if success:
                print("✓ Modelo cargado exitosamente")
                
                # Intentar obtener información del modelo
                try:
                    if hasattr(model, 'GetModelSetting'):
                        setting = model.GetModelSetting()
                        print(f"   ModelSetting: {setting is not None}")
                    
                    if hasattr(model, 'GetModel'):
                        core_model = model.GetModel()
                        print(f"   Core Model: {core_model is not None}")
                        
                except Exception as e:
                    print(f"   Error obteniendo info del modelo: {e}")
                    
            else:
                print("❌ Error: LoadModelJson retornó False")
                
        except Exception as e:
            print(f"❌ Excepción durante la carga: {e}")
            traceback.print_exc()
        
        return success if 'success' in locals() else False
        
    except Exception as e:
        print(f"Error en test de carga: {e}")
        traceback.print_exc()
        return False
    
    finally:
        try:
            live2d.dispose()
            print("Live2D Framework limpiado")
        except:
            pass


def main():
    """Función principal de debug"""
    print("DEBUG DEL MODELO LIVE2D")
    print("=" * 50)
    
    # Verificar archivos
    files_ok = check_model_files()
    
    if files_ok:
        print("\n✓ Todos los archivos necesarios están presentes")
        
        # Probar carga
        load_ok = test_model_loading()
        
        if load_ok:
            print("\n🎉 ¡Modelo se carga correctamente!")
            print("El problema podría estar en la inicialización de OpenGL.")
        else:
            print("\n❌ Problema al cargar el modelo")
            print("Revisa los logs arriba para más detalles.")
    else:
        print("\n❌ Faltan archivos necesarios para el modelo")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())