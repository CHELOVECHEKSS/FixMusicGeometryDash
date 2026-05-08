    import requests
    import os
    from pathlib import Path
    import sys
    from colorama import Fore, Back, Style, init
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading

    init(autoreset=True)
    LOCALAPPDATA = os.getenv('LOCALAPPDATA')
    SAVE_PATH = os.path.join(LOCALAPPDATA, "GeometryDash")
    os.makedirs(SAVE_PATH, exist_ok=True)
    SERVER_URL = "http://localhost:1700"
    MAX_UPLOAD_THREADS = 9999  # Максимальное количество потоков для загрузки

    def clear_screen():
        os.system('cls' if os.name == 'nt' else 'clear')

    def upload_single_file(filepath, filename, music_id, server_url, progress_lock, counters):
        """Загружает один файл на сервер"""
        try:
            with open(filepath, 'rb') as f:
                files = {'file': (filename, f, 'audio/mpeg')}
                response = requests.post(f"{server_url}/upload/{music_id}", files=files, timeout=30)
                
                # DEBUG: Временная отладка
                if response.status_code != 200:
                    with progress_lock:
                        print(f"\n{Fore.RED}DEBUG [{music_id}]: HTTP {response.status_code} - {response.text[:200]}{Style.RESET_ALL}")
                        counters['failed'] += 1
                    return 'failed'
                
                try:
                    result = response.json()
                    with progress_lock:
                        if result.get('status') == 'uploaded':
                            counters['uploaded'] += 1
                            return 'uploaded'
                        elif result.get('status') == 'already_exists':
                            counters['skipped'] += 1
                            return 'exists'
                        else:
                            # Неизвестный статус
                            print(f"\n{Fore.YELLOW}DEBUG [{music_id}]: Неизвестный статус - {result}{Style.RESET_ALL}")
                            counters['failed'] += 1
                            return 'failed'
                except Exception as json_error:
                    # Ошибка парсинга JSON
                    with progress_lock:
                        print(f"\n{Fore.RED}DEBUG [{music_id}]: JSON error - {response.text[:200]}{Style.RESET_ALL}")
                        counters['failed'] += 1
                    return 'failed'
        except Exception as e:
            with progress_lock:
                print(f"\n{Fore.RED}DEBUG [{music_id}]: Exception - {str(e)[:200]}{Style.RESET_ALL}")
                counters['failed'] += 1
            return 'failed'

    def update_progress_bar(current, total, counters, bar_length=40):
        """Обновляет прогресс-бар загрузки"""
        percent = (current / total) * 100 if total > 0 else 0
        filled = int(bar_length * current / total) if total > 0 else 0
        bar = f'{Fore.GREEN}█{Style.RESET_ALL}' * filled + f'{Fore.LIGHTBLACK_EX}░{Style.RESET_ALL}' * (bar_length - filled)
        
        status = f"{Fore.CYAN}Загружено: {counters['uploaded']}{Style.RESET_ALL} | {Fore.YELLOW}Пропущено: {counters['skipped']}{Style.RESET_ALL} | {Fore.RED}Ошибок: {counters['failed']}{Style.RESET_ALL}"
        
        sys.stdout.write(f'\r[{bar}] {Fore.CYAN}{percent:.1f}%{Style.RESET_ALL} ({current}/{total}) | {status}')
        sys.stdout.flush()

    def upload_local_music_to_server(server_url, max_workers=MAX_UPLOAD_THREADS):
        """Загружает всю локальную музыку на сервер с многопоточностью"""
        try:
            all_files = [f for f in os.listdir(SAVE_PATH) if f.endswith(('.mp3', '.wav', '.ogg'))]
            
            if not all_files:
                print(f"{Fore.YELLOW}⚠ Нет локальных файлов для загрузки{Style.RESET_ALL}")
                return
            
            # Фильтруем только музыку (исключаем SFX с префиксом 's')
            music_files = [f for f in all_files if not f.startswith('s')]
            
            if not music_files:
                print(f"{Fore.YELLOW}⚠ Нет музыкальных файлов для загрузки (только SFX){Style.RESET_ALL}")
                return
            
            sfx_count = len(all_files) - len(music_files)
            print(f"{Fore.CYAN}📤 Найдено {len(music_files)} музыкальных файлов для загрузки{Style.RESET_ALL}")
            if sfx_count > 0:
                print(f"{Fore.LIGHTBLACK_EX}   (пропущено {sfx_count} SFX эффектов){Style.RESET_ALL}")
            
            counters = {'uploaded': 0, 'skipped': 0, 'failed': 0, 'processed': 0}
            progress_lock = threading.Lock()
            
            # Подготовка задач
            tasks = []
            for filename in music_files:
                filepath = os.path.join(SAVE_PATH, filename)
                music_id = os.path.splitext(filename)[0]
                
                # Проверяем что music_id это число
                if not music_id.isdigit():
                    counters['skipped'] += 1
                    continue
                
                tasks.append((filepath, filename, music_id))
            
            if not tasks:
                print(f"{Fore.YELLOW}⚠ Нет файлов для загрузки{Style.RESET_ALL}")
                return
            
            # Динамически подстраиваем количество потоков под количество файлов
            optimal_workers = min(len(tasks), max_workers)
            print(f"{Fore.CYAN}🔄 Используется {optimal_workers} потоков для загрузки{Style.RESET_ALL}\n")
            
            total_tasks = len(tasks)
            update_progress_bar(0, total_tasks, counters)
            
            # Многопоточная загрузка
            with ThreadPoolExecutor(max_workers=optimal_workers) as executor:
                futures = [
                    executor.submit(upload_single_file, filepath, filename, music_id, server_url, progress_lock, counters)
                    for filepath, filename, music_id in tasks
                ]
                
                # Ждём завершения всех задач с обновлением прогресс-бара
                for future in as_completed(futures):
                    future.result()
                    with progress_lock:
                        counters['processed'] += 1
                        update_progress_bar(counters['processed'], total_tasks, counters)
            
            print(f"\n\n{Fore.CYAN}📊 Итого: загружено {counters['uploaded']}, пропущено {counters['skipped']}, ошибок {counters['failed']}{Style.RESET_ALL}")
            
        except Exception as e:
            print(f"\n{Fore.RED}✗ Ошибка при загрузке файлов: {e}{Style.RESET_ALL}")

    def download_with_progress(music_id, server_url, consent):
        try:
            print(f"{Fore.YELLOW}⏳ Скачивание музыки ID: {music_id}...{Style.RESET_ALL}")
            response = requests.get(f"{server_url}/download/{music_id}", stream=True, timeout=30)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
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
            
            # Загружаем файл на сервер если пользователь дал согласие
            if consent == 'y':
                print(f"{Fore.YELLOW}⏫ Загрузка музыки на сервер для других пользователей...{Style.RESET_ALL}")
                try:
                    with open(filepath, 'rb') as f:
                        files = {'file': (filename, f, f'audio/{extension}')}
                        upload_response = requests.post(
                            f"{server_url}/upload/{music_id}",
                            files=files,
                            timeout=60
                        )
                        upload_response.raise_for_status()
                        result = upload_response.json()
                        if result.get('status') == 'uploaded':
                            print(f"{Fore.GREEN}✓ Музыка успешно загружена на сервер!{Style.RESET_ALL}")
                        elif result.get('status') == 'already_exists':
                            print(f"{Fore.CYAN}ℹ Музыка уже есть на сервере{Style.RESET_ALL}")
                except Exception as upload_error:
                    print(f"{Fore.RED}✗ Ошибка загрузки на сервер: {upload_error}{Style.RESET_ALL}")
            
            input(f"\n{Fore.YELLOW}Нажмите Enter для продолжения...{Style.RESET_ALL}")
            clear_screen()
        except requests.exceptions.ConnectionError:
            print(f"{Fore.RED}✗ [SERVERERROR] Ошибка подключения к серверу{Style.RESET_ALL}")
            print(f"{Fore.RED}  Убедитесь, что сервер запущен на {SERVER_URL}{Style.RESET_ALL}\n")
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            try:
                error_msg = e.response.json().get('error', 'Неизвестная ошибка')
            except:
                error_msg = str(e)
            
            if status_code == 403:
                print(f"{Fore.RED}✗ [CAPTCHAFALLED] Капча не пройдена{Style.RESET_ALL}")
                print(f"{Fore.LIGHTBLACK_EX}  Подробности: {error_msg}{Style.RESET_ALL}\n")
            elif status_code == 404:
                print(f"{Fore.RED}✗ [MUSICNOTFOUND] Музыка не найдена{Style.RESET_ALL}")
                print(f"{Fore.LIGHTBLACK_EX}  Подробности: {error_msg}{Style.RESET_ALL}\n")
            elif status_code == 400:
                print(f"{Fore.RED}✗ [SERVERNEWGROUNDERROR] Ошибка загрузки с Newgrounds{Style.RESET_ALL}")
                print(f"{Fore.LIGHTBLACK_EX}  Подробности: {error_msg}{Style.RESET_ALL}\n")
            else:
                print(f"{Fore.RED}✗ [SERVERERROR] Ошибка сервера (HTTP {status_code}){Style.RESET_ALL}")
                print(f"{Fore.LIGHTBLACK_EX}  Подробности: {error_msg}{Style.RESET_ALL}\n")
        except Exception as e:
            print(f"{Fore.RED}✗ [UNKNOWNERROR] Неизвестная ошибка{Style.RESET_ALL}")
            print(f"{Fore.LIGHTBLACK_EX}  Подробности: {e}{Style.RESET_ALL}\n")

    def main():
        clear_screen()
        print(f"{Fore.CYAN}{Back.BLACK}=== Клиент скачивания музыки Geometry Dash ==={Style.RESET_ALL}")
        print(f"{Fore.MAGENTA}📁 Папка сохранения: {SAVE_PATH}{Style.RESET_ALL}\n")
        
        # Запрос разрешения на загрузку музыки на сервер
        consent = input(f"{Fore.YELLOW}Для помощи нашему проекту мы хотим чтобы вы разрешили скачать вашу скачанную музыку на наш сервер чтобы другие пользователи могли получать доступ без ограничений.\nРазрешить? (y/n): {Style.RESET_ALL}").strip().lower()
        
        if consent == 'y':
            print(f"\n{Fore.GREEN}✓ Спасибо! Загружаем вашу музыку на сервер...{Style.RESET_ALL}\n")
            upload_local_music_to_server(SERVER_URL)
            input(f"\n{Fore.YELLOW}Нажмите Enter для продолжения...{Style.RESET_ALL}")
            clear_screen()
        else:
            print(f"\n{Fore.YELLOW}⚠ Вы отказались от загрузки. Продолжаем работу...{Style.RESET_ALL}\n")
        
        while True:
            try:
                music_id = input(f"{Fore.YELLOW}Введите ID музыки (или 'выход' для выхода): {Style.RESET_ALL}").strip()
                if music_id.lower() == 'выход':
                    print(f"{Fore.CYAN}До свидания!{Style.RESET_ALL}")
                    break
                if not music_id.isdigit():
                    print(f"{Fore.RED}✗ ID должен быть числом!{Style.RESET_ALL}\n")
                    continue
                download_with_progress(music_id, SERVER_URL, consent)
            except KeyboardInterrupt:
                print(f"\n{Fore.CYAN}Программа прервана.{Style.RESET_ALL}")
                break

    if __name__ == "__main__":
        main()
