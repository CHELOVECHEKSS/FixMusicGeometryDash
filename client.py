import requests
import os
from pathlib import Path
import sys
from colorama import Fore, Back, Style, init

init(autoreset=True)

# Используем %localappdata%
LOCALAPPDATA = os.getenv('LOCALAPPDATA')
SAVE_PATH = os.path.join(LOCALAPPDATA, "GeometryDash")
os.makedirs(SAVE_PATH, exist_ok=True)

SERVER_URL = "http://localhost:5000"

def clear_screen():
    """Очищает экран"""
    os.system('cls' if os.name == 'nt' else 'clear')

def download_with_progress(music_id, server_url):
    """Скачивает музыку с прогресс-баром"""
    try:
        print(f"{Fore.YELLOW}⏳ Скачивание музыки ID: {music_id}...{Style.RESET_ALL}")
        
        response = requests.get(f"{server_url}/download/{music_id}", stream=True, timeout=30)
        response.raise_for_status()
        
        # Получаем размер файла
        total_size = int(response.headers.get('content-length', 0))
        
        # Определяем расширение
        content_type = response.headers.get('content-type', '')
        if 'audio/mpeg' in content_type or 'mp3' in content_type:
            extension = 'mp3'
        elif 'audio/wav' in content_type or 'wav' in content_type:
            extension = 'wav'
        elif 'audio/ogg' in content_type or 'ogg' in content_type:
            extension = 'ogg'
        else:
            extension = 'mp3'
        
        filename = f"{music_id}.{extension}"
        filepath = os.path.join(SAVE_PATH, filename)
        
        # Скачиваем с прогресс-баром
        downloaded = 0
        chunk_size = 8192
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        bar_length = 40
                        filled = int(bar_length * downloaded / total_size)
                        bar = f'{Fore.GREEN}█{Style.RESET_ALL}' * filled + f'{Fore.LIGHTBLACK_EX}░{Style.RESET_ALL}' * (bar_length - filled)
                        
                        mb_downloaded = downloaded / (1024 * 1024)
                        mb_total = total_size / (1024 * 1024)
                        
                        sys.stdout.write(f'\r[{bar}] {Fore.CYAN}{percent:.1f}%{Style.RESET_ALL} ({mb_downloaded:.2f}/{mb_total:.2f} MB)')
                        sys.stdout.flush()
        
        print()
        file_size = os.path.getsize(filepath) / (1024 * 1024)
        print(f"{Fore.GREEN}✓ Музыка скачана: {filename} ({file_size:.2f} MB){Style.RESET_ALL}")
        print(f"{Fore.GREEN}✓ Сохранено в: {filepath}{Style.RESET_ALL}")
        input(f"\n{Fore.YELLOW}Нажмите Enter для продолжения...{Style.RESET_ALL}")
        clear_screen()
        
    except requests.exceptions.ConnectionError:
        print(f"{Fore.RED}✗ Ошибка подключения. Убедитесь, что сервер запущен{Style.RESET_ALL}\n")
    except requests.exceptions.HTTPError as e:
        try:
            error_msg = e.response.json().get('error', 'Неизвестная ошибка')
        except:
            error_msg = str(e)
        print(f"{Fore.RED}✗ Ошибка: {error_msg}{Style.RESET_ALL}\n")
    except Exception as e:
        print(f"{Fore.RED}✗ Ошибка: {e}{Style.RESET_ALL}\n")

def main():
    """Главная функция"""
    clear_screen()
    print(f"{Fore.CYAN}{Back.BLACK}=== Клиент скачивания музыки Geometry Dash ==={Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}📁 Папка сохранения: {SAVE_PATH}{Style.RESET_ALL}\n")
    
    while True:
        try:
            music_id = input(f"{Fore.YELLOW}Введите ID музыки (или 'выход' для выхода): {Style.RESET_ALL}").strip()
            
            if music_id.lower() == 'выход':
                print(f"{Fore.CYAN}До свидания!{Style.RESET_ALL}")
                break
            
            if not music_id.isdigit():
                print(f"{Fore.RED}✗ ID должен быть числом!{Style.RESET_ALL}\n")
                continue
            
            download_with_progress(music_id, SERVER_URL)
        
        except KeyboardInterrupt:
            print(f"\n{Fore.CYAN}Программа прервана.{Style.RESET_ALL}")
            break

if __name__ == "__main__":
    main()
