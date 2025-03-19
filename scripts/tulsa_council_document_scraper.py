#!/usr/bin/env python3
"""
Tulsa City Council Document Scraper

A tool for downloading archived Tulsa City Council meeting minutes (and potentially other supporting documents) by using starting url and going backwards by decrementing item number. Default is hardcoded for most recent document as of 3-15-25.
"""
import requests
from bs4 import BeautifulSoup
import os
import re
import time
import argparse
import logging
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

# Set up logging - console only
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

def extract_pdfs(url, output_dir="downloaded_documents", filter_word=None):
    """
    Extract PDFs from a Tulsa City Council meeting page with optional filtering
    
    Args:
        url (str): The URL of the page
        output_dir (str): Directory to save downloaded PDFs
        filter_word (str): Only download PDFs with this word in the filename. If None, download all PDFs.
    
    Returns:
        int: Number of PDFs downloaded
    """
    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    try:
        logging.info(f"Accessing URL: {url}")
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad responses
        
        # Parse HTML content
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all fileName and pdfString pairs
        file_elements = soup.find_all('div', class_='fileName')
        
        # Check if page has no files
        if not file_elements:
            logging.info(f"No files found on page: {url}")
            return 0
        
        download_count = 0
        
        for file_element in file_elements:
            # Get the filename
            filename = file_element.text.strip()
            
            # Determine if we should download this file based on filter
            should_download = True
            if filter_word:  # Only apply filter if filter_word is not None
                should_download = filter_word.lower() in filename.lower()
            
            if should_download:
                # Get the corresponding document ID
                pdf_string_element = file_element.find_next('div', class_='pdfString')
                if pdf_string_element:
                    document_id = pdf_string_element.text.strip()
                    
                    # Construct the PDF URL
                    pdf_url = f"https://www.cityoftulsa.org/apps/COTDisplayDocument?DocumentType=CouncilDocument&DocumentIdentifiers={document_id}"
                    
                    logging.info(f"Downloading: {filename}")
                    
                    # Download the PDF
                    try:
                        pdf_response = requests.get(pdf_url)
                        pdf_response.raise_for_status()
                        
                        # Clean up filename to ensure it's valid
                        clean_filename = re.sub(r'[\\/*?:"<>|]', "_", filename)
                        
                        # Save the PDF
                        output_path = os.path.join(output_dir, clean_filename)
                        with open(output_path, 'wb') as file:
                            file.write(pdf_response.content)
                        
                        logging.info(f"Successfully downloaded: {output_path}")
                        download_count += 1
                    except requests.exceptions.RequestException as e:
                        logging.error(f"Error downloading {filename}: {e}")
            else:
                logging.debug(f"Skipping file (doesn't contain '{filter_word}'): {filename}")
        
        return download_count
    
    except requests.exceptions.RequestException as e:
        logging.error(f"Error accessing URL {url}: {e}")
        return 0

def decrement_item_in_url(url):
    """
    Decrement the item parameter in the URL
    
    Args:
        url (str): Original URL
    
    Returns:
        str: URL with decremented item parameter, or None if item cannot be decremented
    """
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    
    if 'item' in query_params:
        try:
            item_value = int(query_params['item'][0])
            if item_value <= 1:
                return None  # Can't decrement below 1
            
            # Decrement item value
            query_params['item'] = [str(item_value - 1)]
            
            # Reconstruct the URL
            new_query = urlencode(query_params, doseq=True)
            new_parts = list(parsed_url)
            new_parts[4] = new_query
            return urlunparse(new_parts)
        except ValueError:
            logging.error(f"Error parsing item parameter in URL: {url}")
            return None
    else:
        logging.error(f"No item parameter found in URL: {url}")
        return None

def download_documents(start_url, output_dir="downloaded_documents", max_pages=None, 
                       delay=1, filter_word=None):
    """
    Download council documents recursively by decrementing the item parameter in the URL
    
    Args:
        start_url (str): Starting URL
        output_dir (str): Directory to save downloaded PDFs
        max_pages (int): Maximum number of pages to process, None for indefinite
        delay (int): Seconds to wait between requests to avoid overloading the server
        filter_word (str): Only download PDFs with this word in the filename. If None, download all PDFs.
    """
    current_url = start_url
    page_count = 0
    total_downloads = 0
    
    while current_url and (max_pages is None or page_count < max_pages):
        page_count += 1
        page_msg = f"Processing page {page_count}"
        if max_pages:
            page_msg += f"/{max_pages}"
        logging.info(page_msg)
        
        # Extract PDFs from the current URL
        download_count = extract_pdfs(current_url, output_dir, filter_word)
        total_downloads += download_count
        
        # Decrement the item parameter in the URL
        current_url = decrement_item_in_url(current_url)
        
        # Add a delay to avoid overloading the server
        if current_url:
            time.sleep(delay)
    
    if max_pages and page_count >= max_pages:
        logging.info(f"Reached maximum number of pages ({max_pages}). Stopping.")
    elif not current_url:
        logging.info("No more pages to process. Stopping.")
    
    logging.info(f"Download complete. Processed {page_count} pages. Downloaded {total_downloads} PDFs.")

def main():
    """Main entry point for the script"""
    parser = argparse.ArgumentParser(
        description='Download PDF documents from Tulsa City Council meeting pages recursively',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
            Examples:
            # Download all documents from the last 5 pages
            python tulsa_council_scraper.py --all-documents --max-pages 5
            
            # Download only minutes with default settings
            python tulsa_council_scraper.py
            
            # Download only agendas with custom starting URL
            python tulsa_council_scraper.py --filter "Agenda" --start-url "https://www.cityoftulsa.org/apps/CouncilDocuments?item=45000"
            """
    )
    
    parser.add_argument('--start-url', 
                        default="https://www.cityoftulsa.org/apps/CouncilDocuments?item=47837",
                        help='Starting URL (default: %(default)s)')
    parser.add_argument('--output', default='downloaded_documents',
                        help='Directory to save downloaded PDFs (default: %(default)s)')
    parser.add_argument('--max-pages', type=int, default=None,
                        help='Maximum number of pages to process (default: unlimited)')
    parser.add_argument('--delay', type=int, default=1,
                        help='Delay in seconds between requests (default: %(default)s)')
    parser.add_argument('--filter', default="Minutes",
                        help='Only download PDFs with this word in the filename (default: %(default)s)')
    parser.add_argument('--all-documents', action='store_true',
                        help='Download all documents, ignoring the filter')
    
    args = parser.parse_args()
    
    # If all-documents flag is set, set filter_word to None to download all documents
    filter_word = None if args.all_documents else args.filter
    
    logging.info(f"Starting document download from: {args.start_url}")
    logging.info(f"Output directory: {args.output}")
    
    if args.max_pages:
        logging.info(f"Maximum pages to process: {args.max_pages}")
    else:
        logging.info(f"Maximum pages: Unlimited")
    
    if filter_word:
        logging.info(f"Filter word: {filter_word}")
    else:
        logging.info("No filename filter: downloading all documents")
    
    download_documents(args.start_url, args.output, args.max_pages, args.delay, filter_word)

if __name__ == "__main__":
    main() 