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
import pandas as pd

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
        
        while consecutive_failures < 5:  # Stop after 5 consecutive failures
            # Find currently available cards
            cards = driver.find_elements(By.XPATH, cards_xpath)
            
            # If we've processed all current cards, scroll to load more
            if index >= len(cards):
                print(f"🔄 Scrolling to load more products... (currently found {len(cards)})")
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(3)
                
                # Check for new cards
                new_cards = driver.find_elements(By.XPATH, cards_xpath)
                if len(new_cards) == len(cards):
                    consecutive_failures += 1
                    print(f"⚠ No new products loaded (attempt {consecutive_failures}/5)")
                    time.sleep(2)
                    continue
                else:
                    consecutive_failures = 0
                    cards = new_cards
                    print(f"✅ Found {len(cards)} total products")
            
            if index < len(cards):
                try:
                    card = cards[index]
                    print(f"🖱 Clicking product {index+1}")
                    
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
                    time.sleep(1.5)
                    
                    try:
                        card.click()
                    except:
                        driver.execute_script("arguments[0].click();", card)
                    
                    time.sleep(4)

                    # Scrape product data
                    data = scrape_product_page_data(driver)
                    if data:
                        results.append(data)
                        print(f"Name: {data['product_name']}")
                        if data['available_variants']:
                            print(f"Available Variants: {data['available_variants']}")
                        if data['out_of_stock_variants']:
                            print(f"Out of Stock Variants: {data['out_of_stock_variants']}")
                    else:
                        print(f"⚠ Failed to scrape product {index+1}")
                    
                    print("-" * 50)

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

    # Save to professionally formatted Excel
    if results:
        # Prepare DataFrame with proper structure
        excel_data = []
        for item in results:
            excel_data.append({
                "Product Name": item["product_name"],
                "Available Variants": "; ".join(item["available_variants"]) if item["available_variants"] else "",
                "Out of Stock Variants": "; ".join(item["out_of_stock_variants"]) if item["out_of_stock_variants"] else "",
                "URL": item["url"]
            })
        
        df = pd.DataFrame(excel_data)
        
        # Save to Excel with professional formatting
        excel_filename = f"blinkit_{keyword}.xlsx"
        
        with pd.ExcelWriter(excel_filename, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Products', index=False)
            
            # Get the workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets['Products']
            
            # Auto-adjust column widths
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                
                adjusted_width = min(max_length + 2, 50)  # Cap at 50 characters
                worksheet.column_dimensions[column_letter].width = adjusted_width
            
            # Style the header row
            from openpyxl.styles import Font, PatternFill, Alignment
            
            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            header_alignment = Alignment(horizontal="center", vertical="center")
            
            for cell in worksheet[1]:
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_alignment
        
        print(f"📄 Saved {len(results)} products to Excel: {excel_filename}")
        
        # Print summary
        print(f"\n📊 SUMMARY:")
        print(f"Total products scraped: {len(results)}")
        
        products_with_out_of_stock = [p for p in results if p['out_of_stock_variants']]
        print(f"Products with out-of-stock variants: {len(products_with_out_of_stock)}")
        
        if products_with_out_of_stock:
            print(f"\n🚫 OUT OF STOCK ITEMS:")
            for product in products_with_out_of_stock:
                print(f"• {product['product_name']}: {', '.join(product['out_of_stock_variants'])}")
                
        print(f"\n✅ Professional Excel file ready: {excel_filename}")
        print("📋 The file contains properly formatted columns and can be opened directly in Excel!")
        
    else:
        print("❌ No products scraped")

    return results

if __name__ == "__main__":
    print("🛒 Blinkit Product Scraper - Excel Export")
    print("=" * 40)
    
    # Check if required packages are installed
    try:
        import pandas as pd
        import openpyxl
    except ImportError:
        print("❌ Missing required packages!")
        print("Please install: pip install pandas openpyxl")
        exit()
    
    pincode = input("Enter your pincode: ").strip()
    keyword = input("Enter Blinkit keyword (e.g., milk, himalaya): ").strip()
    
    print(f"\n🚀 Starting scrape for '{keyword}' in {pincode}...")
    
    results = scrape_blinkit(keyword, pincode)
    
    print(f"\n✅ Scraping completed!")
    if results:
        print(f"📁 Check your Excel file: blinkit_{keyword}.xlsx")
     