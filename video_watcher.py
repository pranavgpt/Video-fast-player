import requests
import time
import concurrent.futures
import re
import argparse
import sys
import getpass

# --- Constants ---
BASE_URL = "https://online.vtu.ac.in/api/v1"
DEFAULT_THREADS = 10 

def parse_duration(duration_str):
    """Converts 'HH:MM:SS mins' into total seconds."""
    try:
        numbers = re.findall(r'(\d+)', duration_str)
        if len(numbers) == 3:
            h, m, s = map(int, numbers)
            return h * 3600 + m * 60 + s
        elif len(numbers) == 2:
            m, s = map(int, numbers)
            return m * 60 + s
        return 1800
    except:
        return 1800

def watch_lecture(session, slug, lecture_id, title):
    """Thread function to simulate heartbeats based on exact duration."""
    try:
        detail_url = f"{BASE_URL}/student/my-courses/{slug}/lectures/{lecture_id}"
        detail_res = session.get(detail_url)
        
        if detail_res.status_code != 200:
            return

        lecture_data = detail_res.json().get('data', {})
        duration_str = lecture_data.get('duration', '00:30:00')
        total_seconds = parse_duration(duration_str)
        
        print(f"[*] Started: {title} | Duration: {duration_str}")

        p_url = f"{detail_url}/progress"
        current_time = 0
        heartbeat = 60 
        
        while current_time < (total_seconds + 5):
            current_time += heartbeat
            send_time = min(current_time, total_seconds)
            
            payload = {
                "current_time_seconds": send_time,
                "total_duration_seconds": total_seconds,
                "seconds_just_watched": heartbeat
            }
            
            res = session.post(p_url, json=payload)
            
            if res.status_code == 200:
                if res.json().get('data', {}).get('is_completed'):
                    break
            
            time.sleep(0.1)

        print(f" [✓] Completed: {title}")

    except Exception as e:
        print(f" [X] Error on {title}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Secure VTU Online Class Automation Tool")
    parser.add_argument("-e", "--email", required=True, help="VTU login email")
    
    args = parser.parse_args()

    # Masked password input
    password = getpass.getpass(f"Enter password for {args.email}: ")

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Content-Type": "application/json"
    })

    # 1. Login
    print(f"[*] Logging in as {args.email}...")
    login_res = session.post(f"{BASE_URL}/auth/login", json={"email": args.email, "password": password})
    
    if login_res.status_code != 200:
        print(f"[-] Login failed. Please check your credentials.")
        return

    token = session.cookies.get('access_token')
    if not token:
        print("[-] Access token not found.")
        return

    session.headers.update({"Authorization": f"Bearer {token}"})
    print("[+] Authentication successful.")

    # 2. Fetch Enrolled Courses
    enroll_res = session.get(f"{BASE_URL}/student/my-enrollments")
    enroll_data = enroll_res.json().get('data', [])
    if isinstance(enroll_data, dict): enroll_data = enroll_data.get('data', [])

    lecture_queue = []

    # 3. Scan for Pending Lectures
    for course in enroll_data:
        slug = course.get('details', {}).get('slug')
        if not slug: continue
        
        print(f"[*] Scanning Course: {course['details']['title']}")
        course_res = session.get(f"{BASE_URL}/student/my-courses/{slug}")
        lessons = course_res.json().get('data', {}).get('lessons', [])
        
        for lesson in lessons:
            for lec in lesson.get('lectures', []):
                if not lec.get('is_completed'):
                    lecture_queue.append((slug, lec['id'], lec['title']))

    if not lecture_queue:
        print("[!] No pending lectures found!")
        return

    print(f"\n[+] Total lectures to process: {len(lecture_queue)}")
    print(f"[*] Using {DEFAULT_THREADS} threads concurrently...\n")

    # 4. Multi-threaded Execution
    with concurrent.futures.ThreadPoolExecutor(max_workers=DEFAULT_THREADS) as executor:
        futures = [executor.submit(watch_lecture, session, l[0], l[1], l[2]) for l in lecture_queue]
        concurrent.futures.wait(futures)

    print("\n[!] Done. All lectures updated.")

if __name__ == "__main__":
    main()