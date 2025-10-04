import csv
import os
import sqlite3

from crawlee.crawlers import PlaywrightCrawlingContext
from crawlee.router import Router

# Debug flag - set to True to enable verbose debugging
DEBUG_MODE = False

# Timeout constants (in milliseconds)
PAGE_LOAD_WAIT_TIME = 2000          # Initial page load wait
BUTTON_SCROLL_WAIT_TIME = 500        # Wait after scrolling to button
CONTENT_LOAD_WAIT_TIME = 1000        # Wait after clicking button for content to load
BUTTON_CLICK_TIMEOUT = 5000          # Timeout for individual button clicks
MAX_BUTTON_CLICKS = 20               # Maximum number of "Load more" button clicks

router = Router[PlaywrightCrawlingContext]()

async def load_more_handler(context: PlaywrightCrawlingContext) -> None:
    """Handler to click the 'Load more' button."""
    page = context.page
    
    # Wait for page to load first
    await page.wait_for_timeout(PAGE_LOAD_WAIT_TIME)
    
    # Try multiple selectors for the "Load more" button
    selectors = [
        'div[role="button"]:has-text("Load more")',
        'div[role="button"] >> text=Load more',
        'div:has-text("Load more")',
        'button:has-text("Load more")',
        '[role="button"]:has-text("Load more")'
    ]
    
    load_more_button = None
    for selector in selectors:
        try:
            button = page.locator(selector)
            if await button.count() > 0:
                load_more_button = button.first
                context.log.info(f'Found "Load more" button using selector: {selector}')
                break
        except Exception as e:
            if DEBUG_MODE:
                context.log.info(f'Selector "{selector}" failed: {e}')
            continue
    
    if not load_more_button:
        context.log.warning('No "Load more" button found with any selector')
        return
    
    click_count = 0
    max_clicks = MAX_BUTTON_CLICKS
    previous_cell_count = 0
    
    # Get initial cell count
    initial_cells = page.locator('div[data-row-index]')
    initial_cell_count = await initial_cells.count()
    context.log.info(f'Initial table cells: {initial_cell_count}')
    
    while click_count < max_clicks:
        try:
            # Re-find the button each time in case it changed
            current_button = page.locator('div[role="button"]:has-text("Load more")').first
            
            # Check if button exists
            if await current_button.count() == 0:
                context.log.info(f'No "Load more" button found after {click_count} clicks')
                break
            
            # Scroll to the button to make sure it's in view
            await current_button.scroll_into_view_if_needed()
            await page.wait_for_timeout(BUTTON_SCROLL_WAIT_TIME)
            
            # Check if button is visible
            if not await current_button.is_visible():
                context.log.info(f'Button no longer visible after {click_count} clicks')
                break
            
            # Try to click the button
            context.log.info(f'Attempting to click "Load more" button (click #{click_count + 1})...')
            
            # Try different click methods with shorter timeouts
            click_success = False
            try:
                # Try regular click with timeout
                await current_button.click(timeout=BUTTON_CLICK_TIMEOUT)
                context.log.info(f'Successfully clicked button using .click()')
                click_success = True
            except Exception as e1:
                try:
                    # Try force click with timeout
                    await current_button.click(force=True, timeout=BUTTON_CLICK_TIMEOUT)
                    context.log.info(f'Successfully clicked button using .click(force=True)')
                    click_success = True
                except Exception as e2:
                    try:
                        # Try JavaScript click
                        await page.evaluate('document.querySelector(\'div[role="button"]:has-text("Load more")\')?.click()')
                        context.log.info(f'Successfully clicked button using JavaScript')
                        click_success = True
                    except Exception as e3:
                        context.log.warning(f'All click methods failed, trying to continue: {e1}, {e2}, {e3}')
                        # Don't break, just continue to see if content loaded anyway
                        click_success = True  # Assume success to continue
            
            if not click_success:
                break
                
            click_count += 1
            
            # Wait for content to load
            await page.wait_for_timeout(CONTENT_LOAD_WAIT_TIME)
            
            # Check if new content loaded by counting table cells
            current_cells = page.locator('div[data-row-index]')
            cell_count = await current_cells.count()
            new_cells = cell_count - previous_cell_count
            context.log.info(f'Click #{click_count}: {cell_count} total cells (+{new_cells} new)')
            
            # If no new cells were added, we might have reached the end
            if new_cells == 0 and click_count > 1:
                context.log.info(f'No new cells added after click #{click_count}, stopping')
                break
                
            previous_cell_count = cell_count
            
            # Check if button is still there for next iteration
            if await load_more_button.count() == 0:
                context.log.info(f'Button disappeared after {click_count} clicks')
                break
                
        except Exception as e:
            context.log.error(f'Error clicking "Load more" button on click #{click_count + 1}: {e}')
            break
    
    if click_count >= max_clicks:
        context.log.warning(f'Reached maximum click limit ({max_clicks})')
    
    context.log.info(f'Finished clicking "Load more" button. Total clicks: {click_count}')
    
    
def save_to_database(table, storage_dir):
    """Save the extracted table data to an SQLite database."""
    # Connect to SQLite database (or create it if it doesn't exist)
    db_file_path = os.path.join(storage_dir, 'table_data.db')
    conn = sqlite3.connect(db_file_path)
    cursor = conn.cursor()

    # Create a table if it doesn't already exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS data (
        company TEXT,
        title TEXT,
        tags TEXT,
        year TEXT,
        url TEXT
    )
    ''')

    # Insert the data into the database
    cursor.executemany('INSERT INTO data (company, title, tags, year, url) VALUES (?, ?, ?, ?, ?)', table)

    # Commit changes and close the connection
    conn.commit()
    conn.close()


@router.default_handler
async def default_handler(context: PlaywrightCrawlingContext) -> None:
    """Default request handler."""
    context.log.info(f'Processing {context.request.url} ...')
    
    # Call the load_more_handler
    await load_more_handler(context)

    # Wait for page to load and check for table elements
    page = context.page
    await page.wait_for_timeout(PAGE_LOAD_WAIT_TIME + 1000)  # Extra wait for table elements
    
    if DEBUG_MODE:
        # Debug: Check if the page loaded correctly
        title = await page.title()
        context.log.info(f'Page title: {title}')
        
        # Debug: Check for iframes
        iframes = page.locator('iframe')
        iframe_count = await iframes.count()
        context.log.info(f'Found {iframe_count} iframes on the page')
        
        # Debug: Check for any notion-related elements
        notion_elements = page.locator('[class*="notion"]')
        notion_count = await notion_elements.count()
        context.log.info(f'Found {notion_count} elements with "notion" in class name')
        
        # Debug: Check for table-related elements
        table_elements = page.locator('[class*="table"]')
        table_count = await table_elements.count()
        context.log.info(f'Found {table_count} elements with "table" in class name')
        
        # Debug: Try different selectors
        selectors_to_try = [
            'div.notion-table-view-cell',
            'div[class*="notion-table-view-cell"]',
            'div[data-row-index]',
            'div[data-col-index]',
            '[data-row-index]',
            '[data-col-index]',
            'div[data-row-index="0"]',
            'div[data-col-index="0"]'
        ]
        
        for selector in selectors_to_try:
            elements = page.locator(selector)
            count = await elements.count()
            context.log.info(f'Selector "{selector}": {count} elements found')
            if count > 0:
                # Get the first element's HTML for debugging
                first_element = elements.first
                html = await first_element.inner_html()
                context.log.info(f'First element HTML: {html[:200]}...')
        
        # Debug: Check the page content for any table-related HTML
        page_content = await page.content()
        if 'data-row-index' in page_content:
            context.log.info('Found "data-row-index" in page content')
            # Find the first occurrence
            start = page_content.find('data-row-index')
            snippet = page_content[start-50:start+200]
            context.log.info(f'HTML snippet around data-row-index: {snippet}')
        else:
            context.log.info('No "data-row-index" found in page content')
    
    # Check if table elements exist
    data_elements = page.locator('div[data-row-index]')
    data_count = await data_elements.count()
    context.log.info(f'Found {data_count} table cells with data-row-index')
    
    if data_count == 0:
        # Try to wait a bit more for dynamic content
        try:
            await page.wait_for_selector('div[data-row-index]', timeout=5000)
            data_count = await data_elements.count()
            context.log.info(f'Found {data_count} table cells after waiting')
        except Exception:
            context.log.warning('No table cells found, page may not have loaded properly')
            return

    # Use the data elements we already found
    cells = data_elements
    cell_count = data_count

    # Initialize an empty table to store rows
    table = []

    # Group cells by row index (data-row-index attribute)
    row_indices = set()
    for i in range(cell_count):
        row_index = await cells.nth(i).get_attribute('data-row-index')
        if row_index:
            row_indices.add(int(row_index))
    
    context.log.info(f'Processing {len(row_indices)} rows')
    
    # Process each row
    for row_index in sorted(row_indices):
        try:
            # Get all cells for this row
            row_cells = page.locator(f'div[data-row-index="{row_index}"]')
            cell_count_for_row = await row_cells.count()
            
            if cell_count_for_row < 5:
                context.log.warning(f'Row {row_index} has only {cell_count_for_row} cells, skipping')
                continue

            # Initialize a list to store the row data
            row_data = []

            # Extract text content for the first 2 cells (company and title)
            for j in range(2):
                cell_text = await row_cells.nth(j).inner_text()
                row_data.append(cell_text.strip())

            # Extract tags from the 3rd cell (index 2)
            third_cell = row_cells.nth(2)
            spans = third_cell.locator('span')
            tags_text = " ".join([await spans.nth(k).inner_text() for k in range(await spans.count())])
            row_data.append(tags_text.strip())

            # Extract year from the 4th cell
            year_text = await row_cells.nth(3).inner_text()
            row_data.append(year_text.strip())

            # Extract the href link from the last cell
            last_cell = row_cells.nth(4)
            link = await last_cell.locator('a').get_attribute('href')
            row_data.append(link or '')

            # Append the row data to the table
            table.append(row_data)
            
            # Process and push data for each row
            data = {
                'company': row_data[0],
                'title': row_data[1],
                'tags': row_data[2],
                'year': row_data[3],
                'url': row_data[4],
            }

            # Push the data to the dataset
            await context.push_data(data)
            
        except Exception as e:
            context.log.error(f'Error processing row {row_index}: {e}')
            continue

    context.log.info(f'Successfully extracted {len(table)} rows')
    
    # Save to files if we have data
    if table:
        try:
            # Create storage directory
            storage_dir = 'storage'
            os.makedirs(storage_dir, exist_ok=True)
            
            # Save to CSV file
            csv_file_path = os.path.join(storage_dir, 'table_data.csv')
            with open(csv_file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerows(table)
            
            # Save to database
            save_to_database(table, storage_dir)
            context.log.info(f'Data saved to {storage_dir}/')
        except Exception as e:
            context.log.error(f'Error saving data: {e}')
    else:
        context.log.warning('No table data found to save.')
    
    # await context.enqueue_links()
