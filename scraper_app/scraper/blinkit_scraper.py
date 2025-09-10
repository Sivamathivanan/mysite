from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    ElementClickInterceptedException
)
import time

def get_product_name(driver):
    """Extract product name from page title"""
    title = driver.title or ""
    if " Price" in title:
        return title.split(" Price")[0].strip()
    try:
        return driver.find_element(By.TAG_NAME, "h2").text.strip()
    except:
        return None

def scrape_product_variants(driver):
    """Scrape available and out of stock variants from product page"""
    data = {"available_variants": [], "out_of_stock_variants": []}
    
    try:
        rail = driver.find_element(By.ID, "variant_horizontal_rail")
        buttons = rail.find_elements(
            By.XPATH, './/div[@role="button" and contains(@class,"tw-relative")]'
        )
    except NoSuchElementException:
        buttons = []

    if not buttons:
        # No variants found - check main product stock status
        body = driver.find_element(By.TAG_NAME, "body").text.lower()
        if "out of stock" in body or "currently unavailable" in body:
            data["out_of_stock_variants"].append("Main Product")
        else:
            data["available_variants"].append("Main Product")
        return data

    # Process each variant button
    for btn in buttons:
        lines = btn.text.strip().splitlines()
        # Find line with quantity/size info
        name = next(
            (l for l in lines if any(u in l.lower() for u in ("ml","g","kg","l","piece","pack"))),
            lines[0] if lines else "Unknown"
        ).strip()
        
        combined = " ".join(lines).lower()
        if "out of stock" in combined or "currently unavailable" in combined:
            data["out_of_stock_variants"].append(name)
        else:
            data["available_variants"].append(name)
    
    return data

def scrape_product_page_data(driver):
    """Scrape all product data from current page"""
    try:
        WebDriverWait(driver, 20).until(EC.title_contains("Price"))
        time.sleep(3)
        
        name = get_product_name(driver)
        if not name:
            return None
            
        variants = scrape_product_variants(driver)
        
        return {
            "product_name": name,
            "available_variants": variants["available_variants"],
            "out_of_stock_variants": variants["out_of_stock_variants"],
            "url": driver.current_url
        }
    except:
        return None

def scrape_blinkit(keyword, pincode):
    """Main scraping function"""
    
    # Setup Chrome driver
    driver_path = "C:/Users/sivam/Downloads/chromedriver-win64/chromedriver-win64/chromedriver.exe"
    service = Service(driver_path)
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(60)
    results = []
    
    try:
        # Load search page
        print(f"🔍 Searching for '{keyword}'...")
        driver.get(f"https://www.blinkit.com/s/?q={keyword}")
        
        # Set pincode with retries
        print(f"📍 Setting location to {pincode}...")
        for _ in range(3):
            try:
                inp = WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.XPATH, '//input[@placeholder="search delivery location"]'))
                )
                inp.clear()
                inp.send_keys(pincode)
                sugg = WebDriverWait(driver, 20).until(
                    EC.element_to_be_clickable((By.CLASS_NAME, 'lcVvPT'))
                )
                sugg.click()
                time.sleep(5)
                break
            except (TimeoutException, ElementClickInterceptedException):
                print("⚠ Retrying location setting...")
                time.sleep(3)

        # Wait for initial product cards
        cards_xpath = '//div[@role="button" and contains(@class,"tw-relative tw-flex")]'
        WebDriverWait(driver, 30).until(
            EC.presence_of_all_elements_located((By.XPATH, cards_xpath))
        )
        
        # Give a short sleep then start clicking immediately
        time.sleep(3)
        
        # Start clicking products as they appear
        index = 0
        consecutive_failures = 0
        max_products = 10  # Limit for Django to avoid long waits
        
        while consecutive_failures < 3 and len(results) < max_products:  # Reduced for testing
            # Find currently available cards
            cards = driver.find_elements(By.XPATH, cards_xpath)
            
            if index >= len(cards):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(3)
                
                # Check for new cards
                new_cards = driver.find_elements(By.XPATH, cards_xpath)
                if len(new_cards) == len(cards):
                    consecutive_failures += 1
                    print(f"⚠ No new products loaded (attempt {consecutive_failures}/3)")
                    time.sleep(2)
                    continue
                else:
                    consecutive_failures = 0
                    cards = new_cards
                    print(f"✅ Found {len(cards)} total products")
            
            if index < len(cards) and len(results) < max_products:
                try:
                    card = cards[index]
                    print(f"🖱 Clicking product {index+1}")
                    
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
                    time.sleep(1.5)
                    
                    try:
                        card.click()
                    except:
                        driver.execute_script("arguments.click();", card)
                    
                    time.sleep(4)
                    # Scrape product data
                    data = scrape_product_page_data(driver)
                    if data:
                        results.append(data)
                        print(f"✅ Scraped: {data['product_name']}")
                    else:
                        print(f"⚠ Failed to scrape product {index+1}")
                    
                    # Go back to product list
                    driver.back()
                    try:
                        WebDriverWait(driver, 30).until(
                            EC.presence_of_all_elements_located((By.XPATH, cards_xpath))
                        )
                    except TimeoutException:
                        print("⚠ Timeout going back, refreshing page...")
                        driver.get(f"https://www.blinkit.com/s/?q={keyword}")
                        WebDriverWait(driver, 30).until(
                            EC.presence_of_all_elements_located((By.XPATH, cards_xpath))
                        )
                    
                    time.sleep(2)
                    index += 1
                    consecutive_failures = 0
                    
                except Exception as e:
                    print(f"⚠ Error with product {index+1}: {str(e)}")
                    index += 1
                    consecutive_failures += 1
                    
                    try:
                        driver.get(f"https://www.blinkit.com/s/?q={keyword}")
                        WebDriverWait(driver, 30).until(
                            EC.presence_of_all_elements_located((By.XPATH, cards_xpath))
                        )
                        time.sleep(2)
                    except:
                        print("❌ Failed to recover")
                        break
        
        print(f"🏁 Finished scraping. Found {len(results)} products total.")
        
    finally:
        print("🧹 Closing browser...")
        driver.quit()
    
    return results
