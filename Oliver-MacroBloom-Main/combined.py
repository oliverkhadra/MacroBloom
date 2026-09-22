from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
import time
import os
import csv
import random # For random delays to mimic human behavior

# --- Configuration ---
GECKODRIVER_PATH = r"C:\Users\Home PC Office\Desktop\yahoo scraping\geckodriver.exe" # <--- **ENSURE THIS IS YOUR CORRECT PATH**
OUTPUT_CSV_FILE = "yahoo_environmental_scores_multi_page.csv" 
SCREENER_BASE_URL = "https://finance.yahoo.com/research-hub/screener/most_actives/" # Base URL for screener
TICKERS_PER_PAGE = 100 # Yahoo Finance displays 100 tickers per page
MAX_PAGES_TO_SCRAPE_FOR_TICKERS = 30 # Safety limit: Stop after this many pages for ticker collection

# --- Helper Functions ---

def handle_cookie_consent(driver_obj):
    """
    Checks for and prompts user to handle cookie consent pop-up.
    """
    try:
        print("\nChecking for cookie consent pop-up...")
        # Check for a common button on Yahoo's cookie consent
        WebDriverWait(driver_obj, 5).until(
            EC.presence_of_element_located((By.XPATH, "//button[@name='agree']"))
        )
        print("\n#####################################################")
        print("### !!! IMPORTANT: COOKIE CONSENT POP-UP DETECTED !!! ###")
        print("### Please go to the Firefox window that just opened. ###")
        print("### Manually click the 'Accept All' or 'Agree' button ###")
        print("### on the cookie consent banner.                     ###")
        print("### AFTER you have clicked it, come back to THIS terminal ###")
        print("### and press the ENTER key to continue the script.   ###")
        print("#####################################################\n")
        input("Press Enter to continue after handling cookies...")
        print("Resuming script after manual cookie consent handling.")
        time.sleep(random.uniform(2, 4)) # Small delay after user input
    except TimeoutException:
        print("No cookie consent pop-up or 'Accept all' button found within timeout. Continuing automatically.")
    except NoSuchElementException:
        print("Cookie consent button not found by expected XPATH. Continuing automatically.")
    except Exception as e:
        print(f"An unexpected error occurred during initial cookie check: {e}")

def scrape_tickers_from_current_screener_page(driver_obj):
    """
    Scrapes ticker symbols from the currently loaded Yahoo Finance screener page.
    Returns a list of tickers.
    """
    current_page_tickers = []
    try:
        # Wait for ticker elements to be present
        # Increased wait time for robustness
        WebDriverWait(driver_obj, 20).until(
            EC.presence_of_element_located((By.XPATH, "//span[contains(@class, 'symbol')]"))
        )
        # Find all ticker elements
        ticker_elements = driver_obj.find_elements(By.XPATH, "//span[contains(@class, 'symbol')]")
        
        if ticker_elements:
            print(f"  Found {len(ticker_elements)} potential ticker elements on the current page.")
            for element in ticker_elements:
                ticker = element.text.strip()
                if ticker: # Ensure ticker is not empty
                    current_page_tickers.append(ticker)
            print(f"  Extracted {len(current_page_tickers)} valid tickers from this page.")
        else:
            print(f"  No ticker symbols found on this page.")
    except TimeoutException:
        print(f"  !!! WARNING: Timeout waiting for tickers on current page. No tickers scraped. !!!")
    except Exception as e:
        print(f"  An error occurred while scraping tickers from current page: {e}")
    return current_page_tickers

def get_environmental_score_for_ticker(driver_obj, ticker: str):
    """
    Navigates to a ticker's Yahoo Finance sustainability page and extracts its
    Environmental Risk Score using a shared WebDriver instance.
    Returns the score or an error message.
    """
    url = f"https://finance.yahoo.com/quote/{ticker}/sustainability"
    print(f"  Attempting to get score for: {ticker} from {url}")

    try:
        driver_obj.get(url)
        # Give page some time to load after navigation
        time.sleep(random.uniform(3, 6)) # Random delay after navigating to sustainability page

        environmental_score = "Not Found" # Default value

        # Wait for the main Environmental Risk Score section to load
        environmental_section_locator = (By.XPATH, "//section[@data-testid='ENVIRONMENTAL_SCORE']")
        
        try:
            environmental_section = WebDriverWait(driver_obj, 15).until( # Increased wait time
                EC.presence_of_element_located(environmental_section_locator)
            )
            # Find the score within that section
            score_element = environmental_section.find_element(By.TAG_NAME, "h4")
            environmental_score = score_element.text.strip()
            print(f"    SUCCESS: {ticker} Environmental Score: {environmental_score}")
        except TimeoutException:
            environmental_score = "Error: Environmental Score section did not load within timeout."
            print(f"    FAIL: {ticker} - {environmental_score}")
        except NoSuchElementException:
            environmental_score = "Error: Score H4 element not found in Environmental Score section."
            print(f"    FAIL: {ticker} - {environmental_score}")
        except Exception as e:
            environmental_score = f"Error: Failed to extract score ({str(e)})"
            print(f"    FAIL: {ticker} - {environmental_score}")
        
        return environmental_score

    except WebDriverException as e:
        # Catch common WebDriver issues like page not loading, connection lost
        error_msg = f"WebDriver Error during score scrape for {ticker}: {str(e).splitlines()[0]}"
        print(f"    CRITICAL WEBDRIVER ERROR for {ticker}: {error_msg}")
        return error_msg
    except Exception as e:
        return f"Unhandled Error during score scrape for {ticker}: {str(e)}"

# --- Main Scraper Logic ---

def scrape_yahoo_finance_data():
    """
    Executes the two-phase scraping process:
    1. Collects all tickers from multiple screener pages.
    2. Fetches environmental scores for each collected ticker.
    """
    if not os.path.exists(GECKODRIVER_PATH):
        print("\n!!! ERROR: GECKODRIVER PATH IS INCORRECT OR FILE NOT FOUND !!!")
        print(f"Expected geckodriver at: {GECKODRIVER_PATH}")
        input("Press Enter to exit the script and fix the path...")
        return

    print(f"\n--- Starting Yahoo Finance Data Scraper ---")
    print(f"Results will be saved to: {OUTPUT_CSV_FILE}")

    service = Service(GECKODRIVER_PATH)
    driver_instance = None
    all_results = []
    headers = ["Ticker", "Environmental Score", "Status/Error"]
    all_results.append(headers) # Add headers to the results list
    all_scraped_tickers = [] # List to store all unique tickers found

    try:
        # --- Launch Firefox Browser ---
        print("Launching Firefox browser...")
        driver_instance = webdriver.Firefox(service=service)
        driver_instance.set_window_size(1920, 1080)
        
        # --- Phase 1: Collect All Tickers from Screener Pages ---
        print("\n--- Phase 1: Collecting Tickers from Screener Pages ---")
        page_num = 0
        while page_num < MAX_PAGES_TO_SCRAPE_FOR_TICKERS:
            page_num += 1
            start_index = (page_num - 1) * TICKERS_PER_PAGE
            screener_url = f"{SCREENER_BASE_URL}?start={start_index}&count={TICKERS_PER_PAGE}"
            
            print(f"\nNavigating to screener Page {page_num}: {screener_url}")
            driver_instance.get(screener_url)
            
            # Initial longer delay for the very first page load
            if page_num == 1:
                time.sleep(random.uniform(25, 30))
                handle_cookie_consent(driver_instance) # Handle cookies only once
            else:
                # Shorter delay for subsequent screener page loads
                time.sleep(random.uniform(5, 10)) 

            current_page_tickers = scrape_tickers_from_current_screener_page(driver_instance)
            
            if not current_page_tickers:
                print(f"No tickers found on Page {page_num}. Assuming end of screener data or an issue. Stopping ticker collection.")
                break # Exit ticker collection loop if no tickers are found

            # Add unique tickers to the master list
            for ticker in current_page_tickers:
                if ticker not in all_scraped_tickers:
                    all_scraped_tickers.append(ticker)
            
            print(f"Total unique tickers collected so far: {len(all_scraped_tickers)}")

            # If the current page yielded fewer than 100 tickers, it's likely the last one
            if len(current_page_tickers) < TICKERS_PER_PAGE:
                print(f"Detected fewer than {TICKERS_PER_PAGE} tickers on Page {page_num}. Assuming this is the LAST PARTIAL PAGE. Stopping ticker collection.")
                break
            
            # Add a delay before navigating to the next screener page
            if page_num < MAX_PAGES_TO_SCRAPE_FOR_TICKERS:
                print(f"  Waiting {random.uniform(3, 7):.1f} seconds before loading next screener page...")
                time.sleep(random.uniform(3, 7))

        print(f"\n--- Phase 1 Complete: Collected {len(all_scraped_tickers)} unique tickers. ---")

        # --- Phase 2: Fetch Environmental Scores for Collected Tickers ---
        if not all_scraped_tickers:
            print("No tickers were collected in Phase 1. Skipping Phase 2 (score collection).")
            return

        print("\n--- Phase 2: Fetching Environmental Scores for Each Ticker ---")
        
        for i, ticker in enumerate(all_scraped_tickers):
            print(f"\nProcessing ticker {i+1}/{len(all_scraped_tickers)}: {ticker}")
            score = get_environmental_score_for_ticker(driver_instance, ticker)
            
            # Store results
            status_error = "Success" if "Error" not in score else score
            result_row = [ticker, score if "Error" not in score else "", status_error]
            all_results.append(result_row)

            # --- CRITICAL DELAY TO MIMIC HUMAN BEHAVIOR ---
            # Random delay between 5 and 8 seconds after each ticker's score scrape.
            delay_between_tickers = random.uniform(5,8)
            print(f"  Waiting {delay_between_tickers:.1f} seconds before next ticker\'s page navigation...")
            time.sleep(delay_between_tickers)

    except KeyboardInterrupt:
        print("\nScript interrupted by user (Ctrl+C). Saving current results...")
    except Exception as e:
        print(f"\n!!! AN UNHANDLED CRITICAL ERROR OCCURRED: {type(e).__name__}: {e} !!!")
    finally:
        if driver_instance:
            print("\nClosing Firefox browser.")
            driver_instance.quit()
        
        # Save results to CSV even if interrupted or errors occur
        with open(OUTPUT_CSV_FILE, 'w', newline='', encoding='utf-8') as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerows(all_results)
        print(f"\n--- Scraping Process Finished ---")
        print(f"Results saved to '{OUTPUT_CSV_FILE}'")
        print(f"Total entries saved to CSV (including headers): {len(all_results)}")
        print(f"Number of tickers for which score was attempted: {len(all_results) - 1}") # Minus headers

    print("\nScript execution finished.")

# --- Run the combined scrape ---
if __name__ == "__main__":
    scrape_yahoo_finance_data()