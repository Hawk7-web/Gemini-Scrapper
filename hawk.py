from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
import time
import re

console = Console()

class GeminiChat:
    def __init__(self):
        self.driver = None
        self.setup_driver()
    
    def setup_driver(self):
        """Setup Chrome driver with stealth options"""
        chrome_options = Options()
        
        # Headless mode - no browser window
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--window-size=1920,1080")
        
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            '''
        })
    
    def open_gemini(self):
        """Open Gemini chat interface"""
        console.print("[bold cyan]Opening Gemini...[/bold cyan]")
        self.driver.get("https://gemini.google.com/app")
        
        # Wait for page to load
        time.sleep(5)
        console.print("[bold yellow]Page loaded. Waiting for full initialization...[/bold yellow]")
        time.sleep(15)
    
    def is_comparison_question(self, question):
        """Detect if question is asking for comparison"""
        keywords = [
            'difference', 'compare', 'comparison', 'vs', 'versus',
            'better', 'contrast', 'distinguish', 'differentiate',
            'pros and cons', 'advantages', 'disadvantages', 'benefits',
            'between', 'differ'
        ]
        return any(keyword in question.lower() for keyword in keywords)
    
    def send_question(self, question):
        """Send question to Gemini with table formatting request if needed"""
        # Enhance question for comparison queries
        enhanced_question = question
        if self.is_comparison_question(question):
            enhanced_question = f"""{question}

IMPORTANT: Provide your answer ONLY as a markdown table with clear side-by-side comparison. 
Format like this:

| Feature/Aspect | First Item | Second Item |
|----------------|------------|-------------|
| Category 1     | Details    | Details     |
| Category 2     | Details    | Details     |
| Category 3     | Details    | Details     |

Do NOT write paragraphs. ONLY respond with the comparison table.
"""
        
        console.print(f"\n[cyan]Sending:[/cyan] {question}")
        
        # Method: Pure JavaScript - most reliable for dynamic pages
        try:
            # Wait for page to be ready
            time.sleep(2)
            
            # Use JavaScript to interact with the page directly
            js_send_script = """
                // Find the input element
                let inputElement = null;
                let richTextarea = document.querySelector('rich-textarea');
                
                if (richTextarea) {
                    inputElement = richTextarea.querySelector('p[contenteditable="true"]') ||
                                  richTextarea.querySelector('div[contenteditable="true"]') ||
                                  richTextarea.querySelector('[contenteditable="true"]');
                }
                
                if (!inputElement) {
                    inputElement = document.querySelector('[contenteditable="true"]');
                }
                
                if (inputElement) {
                    // Focus and set text
                    inputElement.focus();
                    inputElement.textContent = arguments[0];
                    
                    // Trigger events
                    inputElement.dispatchEvent(new Event('input', { bubbles: true }));
                    inputElement.dispatchEvent(new Event('change', { bubbles: true }));
                    
                    // Wait a bit then submit
                    setTimeout(() => {
                        // Try to find and click send button
                        let sendButton = document.querySelector('button[aria-label*="Send"]') ||
                                        document.querySelector('button[type="submit"]') ||
                                        Array.from(document.querySelectorAll('button')).find(btn => 
                                            btn.getAttribute('aria-label')?.includes('Send') ||
                                            btn.textContent.includes('Send')
                                        );
                        
                        if (sendButton) {
                            sendButton.click();
                        } else {
                            // Fallback: trigger Enter key
                            let event = new KeyboardEvent('keydown', {
                                key: 'Enter',
                                code: 'Enter',
                                keyCode: 13,
                                which: 13,
                                bubbles: true
                            });
                            inputElement.dispatchEvent(event);
                        }
                    }, 500);
                    
                    return true;
                }
                return false;
            """
            
            result = self.driver.execute_script(js_send_script, enhanced_question)
            
            if result:
                console.print("[green]✓ Message sent successfully[/green]")
                time.sleep(2)  # Wait for submission
                return True
            else:
                console.print("[red]❌ Could not find input element[/red]")
                return False
                
        except Exception as e:
            console.print(f"[red]Error sending message: {e}[/red]")
            return False
    
    def wait_for_response(self, timeout=60):
        """Wait for Gemini to finish responding"""
        with console.status("[cyan]🤔 Thinking...[/cyan]", spinner="dots"):
            start_time = time.time()
            last_length = 0
            stable_count = 0
            
            while time.time() - start_time < timeout:
                try:
                    body_text = self.driver.find_element(By.TAG_NAME, "body").text
                    current_length = len(body_text)
                    
                    if current_length == last_length:
                        stable_count += 1
                        if stable_count >= 3:
                            time.sleep(2)
                            return True
                    else:
                        stable_count = 0
                        last_length = current_length
                    
                except Exception as e:
                    pass
                
                time.sleep(2)
            
            return True
    
    def get_response(self):
        """Extract the latest response from Gemini using JavaScript"""
        try:
            time.sleep(3)  # Extra wait for content to render
            
            # Use JavaScript to extract the latest response
            js_extract_script = """
                // Try multiple strategies to find the response
                
                // Strategy 1: Look for message-content elements
                let messageContents = document.querySelectorAll('message-content');
                if (messageContents.length > 0) {
                    let lastMessage = messageContents[messageContents.length - 1];
                    return lastMessage.innerText || lastMessage.textContent;
                }
                
                // Strategy 2: Look for model response containers
                let modelResponses = document.querySelectorAll('[class*="model-response"], [class*="response-container"]');
                if (modelResponses.length > 0) {
                    let lastResponse = modelResponses[modelResponses.length - 1];
                    return lastResponse.innerText || lastResponse.textContent;
                }
                
                // Strategy 3: Look for any message-like divs
                let allMessages = document.querySelectorAll('[class*="message"]');
                if (allMessages.length > 0) {
                    // Get the last few messages and filter out user messages
                    let messages = Array.from(allMessages).slice(-5);
                    for (let i = messages.length - 1; i >= 0; i--) {
                        let text = messages[i].innerText || messages[i].textContent;
                        if (text && text.length > 30) {
                            return text;
                        }
                    }
                }
                
                // Strategy 4: Look for markdown content
                let markdownElements = document.querySelectorAll('[class*="markdown"], .response-text');
                if (markdownElements.length > 0) {
                    let lastMarkdown = markdownElements[markdownElements.length - 1];
                    return lastMarkdown.innerText || lastMarkdown.textContent;
                }
                
                return null;
            """
            
            response = self.driver.execute_script(js_extract_script)
            
            if response and len(response.strip()) > 20:
                return response.strip()
            
            # Final fallback: get page text and parse
            console.print("[yellow]Using fallback extraction...[/yellow]")
            body = self.driver.find_element(By.TAG_NAME, "body")
            full_text = body.text
            lines = full_text.split('\n')
            response_lines = []
            skip_keywords = ['gemini', 'google', 'sign in', 'menu', 'settings', 'new chat', 'send', 'type']
            
            for line in lines:
                line = line.strip()
                if len(line) > 20 and not any(kw in line.lower() for kw in skip_keywords):
                    response_lines.append(line)
            
            if response_lines:
                # Return last substantial block
                return '\n'.join(response_lines[-10:])
            
            return "⚠️ Could not extract response. The page may still be loading."
            
        except Exception as e:
            console.print(f"[red]Extraction error: {e}[/red]")
            return f"⚠️ Error extracting response: {e}"
    
    def ask(self, question):
        """Ask question and get response"""
        if self.send_question(question):
            self.wait_for_response()
            response = self.get_response()
            return response
        return "❌ Failed to send question"
    
    def close(self):
        """Close the browser"""
        if self.driver:
            self.driver.quit()


class ResponseFormatter:
    @staticmethod
    def parse_markdown_table(text):
        """Parse markdown table from response"""
        lines = text.strip().split('\n')
        headers = None
        data = []
        
        for line in lines:
            line = line.strip()
            
            if not line or '|' not in line:
                continue
            
            # Parse cells
            cells = [cell.strip() for cell in line.split('|')]
            cells = [cell for cell in cells if cell]
            
            if not cells:
                continue
            
            # Skip separator lines
            if all(set(cell.replace('-', '').replace(':', '').strip()) == set() for cell in cells):
                continue
            
            if headers is None:
                headers = cells
            else:
                data.append(cells)
        
        return headers, data
    
    @staticmethod
    def create_rich_table(headers, data):
        """Create beautiful rich table"""
        table = Table(
            show_header=True,
            header_style="bold cyan",
            box=box.DOUBLE_EDGE,
            border_style="cyan"
        )
        
        # Add columns with alternating colors
        colors = ["green", "yellow", "blue", "magenta"]
        for i, header in enumerate(headers):
            color = colors[i % len(colors)]
            table.add_column(header, style=color, no_wrap=False, overflow="fold")
        
        # Add rows
        for row in data:
            while len(row) < len(headers):
                row.append("")
            table.add_row(*row[:len(headers)])
        
        return table
    
    @staticmethod
    def display_response(text, question):
        """Display response with smart formatting"""
        console.print()
        
        # Display question
        console.print(Panel(
            f"[bold cyan]Q:[/bold cyan] {question}",
            border_style="cyan",
            box=box.ROUNDED
        ))
        console.print()
        
        # Try to parse as table
        headers, data = ResponseFormatter.parse_markdown_table(text)
        
        if headers and data and len(data) > 0:
            # Display as rich table
            table = ResponseFormatter.create_rich_table(headers, data)
            console.print(Panel(
                table,
                title="[bold green]📊 Comparison Table[/bold green]",
                border_style="green",
                box=box.DOUBLE_EDGE
            ))
        else:
            # Display as regular text with formatting
            console.print(Panel(
                text,
                title="[bold yellow]🤖 Response[/bold yellow]",
                border_style="yellow",
                box=box.ROUNDED
            ))
        
        console.print()


def main():
    # Banner
    console.print()
    console.print("[bold cyan]" + "=" * 60 + "[/bold cyan]")
    console.print("[bold magenta]                🚀 HAWK IS GETTING STARTED 🚀[/bold magenta]")
    console.print("[bold cyan]" + "=" * 60 + "[/bold cyan]")
    console.print()
    
    gemini = GeminiChat()
    formatter = ResponseFormatter()
    
    try:
        gemini.open_gemini()
        
        console.print("[bold green]✅ System Ready! Let's go![/bold green]")
        console.print()
        console.print("[bold cyan]" + "─" * 60 + "[/bold cyan]")
        
        while True:
            console.print()
            question = console.input("[bold cyan]💭 Your question[/bold cyan] ([red]'quit' to exit[/red]): ")
            
            if question.lower() in ['quit', 'exit', 'q']:
                console.print("[yellow]👋 Goodbye![/yellow]")
                break
            
            if not question.strip():
                console.print("[yellow]Please enter a question[/yellow]")
                continue
            
            response = gemini.ask(question)
            formatter.display_response(response, question)
            
            console.print("[dim]" + "─" * 60 + "[/dim]")
    
    except KeyboardInterrupt:
        console.print("\n[yellow]👋 Interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        import traceback
        traceback.print_exc()
    finally:
        console.print("\n[cyan]Closing browser...[/cyan]")
        gemini.close()
        console.print("[green]Done![/green]")


if __name__ == "__main__":
    main()