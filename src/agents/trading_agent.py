"""
🌙 Moon Dev's LLM Trading Agent
Handles all LLM-based trading decisions
"""

# Keep only these prompts
TRADING_PROMPT = """
You are Moon Dev's AI Trading Assistant 🌙

Analyze the provided market data and strategy signals (if available) to make a trading decision.

Market Data Criteria:
1. Price action relative to MA20 and MA40
2. RSI levels and trend
3. Volume patterns
4. Recent price movements

{strategy_context}

Respond in this exact format:
1. First line must be one of: BUY, SELL, or NOTHING (in caps)
2. Then explain your reasoning, including:
   - Technical analysis
   - Strategy signals analysis (if available)
   - Risk factors
   - Market conditions
   - Confidence level (as a percentage, e.g. 75%)

Remember: 
- Moon Dev always prioritizes risk management! 🛡️
- Never trade USDC or SOL directly
- Consider both technical and strategy signals
"""

ALLOCATION_PROMPT = """
You are Moon Dev's Portfolio Allocation Assistant 🌙

Given the total portfolio size and trading recommendations, allocate capital efficiently.
Consider:
1. Position sizing based on confidence levels
2. Risk distribution
3. Keep cash buffer as specified
4. Maximum allocation per position

Format your response as a Python dictionary:
{
    "token_address": allocated_amount,  # In USD
    ...
    "USDC_ADDRESS": remaining_cash  # Always use USDC_ADDRESS for cash
}

Remember:
- Total allocations must not exceed total_size
- Higher confidence should get larger allocations
- Never allocate more than {MAX_POSITION_PERCENTAGE}% to a single position
- Keep at least {CASH_PERCENTAGE}% in USDC as safety buffer
- Only allocate to BUY recommendations
- Cash must be stored as USDC using USDC_ADDRESS: {USDC_ADDRESS}
"""

# import anthropic # Replaced by ModelFactory
import os
import pandas as pd
import json
from termcolor import colored, cprint
# from dotenv import load_dotenv # ModelFactory handles .env loading
from datetime import datetime, timedelta
import time

# Local imports
# Specific imports from config to manage namespace and clarity
from src.config import (
    TRADING_PROMPT as BASE_TRADING_PROMPT,
    ALLOCATION_PROMPT as BASE_ALLOCATION_PROMPT,
    EXCLUDED_TOKENS, MONITORED_TOKENS, USDC_ADDRESS, AI_MODEL, # AI_MODEL is part of config for now
    AI_MAX_TOKENS, AI_TEMPERATURE, usd_size, MAX_POSITION_PERCENTAGE, CASH_PERCENTAGE,
    SLEEP_BETWEEN_RUNS_MINUTES, max_usd_order_size, slippage # Ensure all used config vars are listed
)
from src import nice_funcs as n
from src.data.ohlcv_collector import collect_all_tokens
from src.models.model_factory import model_factory # Import the singleton factory instance

# Prepare prompts using variables from config
# FORMATTED_ALLOCATION_PROMPT_SYSTEM is defined here using imported config vars
FORMATTED_ALLOCATION_PROMPT_SYSTEM = BASE_ALLOCATION_PROMPT.format(
    MAX_POSITION_PERCENTAGE=MAX_POSITION_PERCENTAGE,
    CASH_PERCENTAGE=CASH_PERCENTAGE,
    USDC_ADDRESS=USDC_ADDRESS
)
# BASE_TRADING_PROMPT (originally TRADING_PROMPT from config) will be formatted dynamically
# in analyze_market_data where strategy_context is available.

class TradingAgent:
    def __init__(self):
        cprint("🤖 Initializing Moon Dev's LLM Trading Agent...", "cyan")
        self.ai_model = model_factory.get_core_model()
        if not self.ai_model:
            cprint("❌ CRITICAL: Core AI Model could not be initialized. Trading Agent cannot start.", "red")
            raise RuntimeError("Failed to initialize core AI model for TradingAgent.")

        self.recommendations_df = pd.DataFrame(columns=['token', 'action', 'confidence', 'reasoning'])
        cprint(f"✅ LLM Trading Agent initialized successfully with model: {self.ai_model.model_name} ({self.ai_model.model_type})", "green")

    def analyze_market_data(self, token, market_data):
        """Analyze market data using the configured core AI model"""
        if not self.ai_model:
            cprint(f"❌ AI model not available for analysis of {token}.", "red")
            self.recommendations_df = pd.concat([
                self.recommendations_df,
                pd.DataFrame([{'token': token, 'action': "NOTHING", 'confidence': 0, 'reasoning': "AI model not available during analysis"}])
            ], ignore_index=True)
            return None
        try:
            if token in EXCLUDED_TOKENS:
                cprint(f"⚠️ Skipping analysis for excluded token: {token}", "yellow")
                return None
            
            strategy_context_str = ""
            if 'strategy_signals' in market_data:
                strategy_context_str = f"Strategy Signals Available:\n{json.dumps(market_data['strategy_signals'], indent=2)}"
            else:
                strategy_context_str = "No strategy signals available."

            current_trading_prompt = BASE_TRADING_PROMPT.format(strategy_context=strategy_context_str)
            # Ensure market_data is passed as a string, ideally JSON, for the prompt
            user_prompt_content = f"Market Data to Analyze for {token}:\n{json.dumps(market_data, indent=2)}"

            model_response = self.ai_model.generate_response(
                system_prompt=current_trading_prompt,
                user_content=user_prompt_content,
                temperature=AI_TEMPERATURE, # From src.config
                max_tokens=AI_MAX_TOKENS    # From src.config
            )
            
            if not model_response or not model_response.content:
                cprint(f"❌ Failed to get a valid response from AI model for {token}", "red")
                self.recommendations_df = pd.concat([
                    self.recommendations_df,
                    pd.DataFrame([{'token': token, 'action': "NOTHING", 'confidence': 0, 'reasoning': "AI response error or empty content"}])
                ], ignore_index=True)
                return None

            response_text = model_response.content.strip()
            lines = response_text.split('\n')
            action = lines[0].strip().upper() if lines else "NOTHING" # Ensure action is uppercase
            
            confidence = 0 # Default confidence
            reasoning = '\n'.join(lines[1:]) if len(lines) > 1 else "No detailed reasoning provided"
            
            # More robust confidence extraction
            for line in lines:
                line_lower = line.lower()
                if 'confidence level' in line_lower or 'confidence' in line_lower :
                    try:
                        # Attempt to extract digits before a '%' or from a general statement
                        parts = line_lower.split(':')[-1].split('%')[0] # Handles "Confidence: 75%" or "Confidence level 75"
                        confidence = int(''.join(filter(str.isdigit, parts)))
                        if 0 <= confidence <= 100: # Validate confidence range
                           break # Found valid confidence
                        else:
                           confidence = 50 # Default if out of range
                    except ValueError:
                        confidence = 50 # Default if parsing fails
            
            self.recommendations_df = pd.concat([
                self.recommendations_df,
                pd.DataFrame([{'token': token, 'action': action, 'confidence': confidence, 'reasoning': reasoning}])
            ], ignore_index=True)
            
            cprint(f"🎯 AI Analysis Complete for {token[:4]}: Action: {action}, Confidence: {confidence}%", "green")
            return response_text # Return the text content
            
        except Exception as e:
            cprint(f"❌ Error in AI analysis for {token}: {str(e)}", "red")
            self.recommendations_df = pd.concat([
                self.recommendations_df,
                pd.DataFrame([{
                    'token': token,
                    'action': "NOTHING",
                    'confidence': 0,
                    'reasoning': f"Error during analysis: {str(e)}"
                }])
            ], ignore_index=True)
            return None
    
    def allocate_portfolio(self):
        """Get AI-recommended portfolio allocation using the configured core AI model"""
        if not self.ai_model:
            cprint("❌ AI model not available for portfolio allocation.", "red")
            return None
        try:
            cprint("\n💰 Calculating optimal portfolio allocation...", "cyan")
            max_position_value = usd_size * (MAX_POSITION_PERCENTAGE / 100) # Renamed for clarity
            cprint(f"🎯 Maximum position value: ${max_position_value:.2f} ({MAX_POSITION_PERCENTAGE}% of ${usd_size:.2f})", "cyan")

            # Filter recommendations for BUY signals and sort by confidence
            buy_recommendations = self.recommendations_df[self.recommendations_df['action'] == 'BUY'].sort_values(by='confidence', ascending=False)

            if buy_recommendations.empty:
                cprint("ℹ️ No BUY recommendations available. Allocating all to USDC.", "blue")
                allocations = {USDC_ADDRESS: usd_size}
                cprint("\n📊 Portfolio Allocation:", "green")
                for token, amount in allocations.items(): # Ensure this loop runs
                    token_display = "USDC" if token == USDC_ADDRESS else token
                    cprint(f"  • {token_display}: ${amount:.2f}", "green")
                return allocations

            # Construct user content with dynamic information
            user_content_for_allocation = f"""
Current Portfolio Context:
- Total portfolio value (USD): {usd_size}
- Maximum single position value (USD): {max_position_value}
- Minimum cash buffer to maintain (USDC %): {CASH_PERCENTAGE}
- Monitored token addresses for potential investment: {MONITORED_TOKENS}
  (Note: Only consider tokens from the 'Trading Recommendations' below for actual allocation)
- USDC Address for cash: {USDC_ADDRESS}

Trading Recommendations (BUY signals only, sorted by confidence):
{buy_recommendations.to_json(orient='records', indent=2)}

Please provide the portfolio allocation based on these recommendations and the rules defined in the system prompt.
Ensure the output is a valid JSON object.
"""
            model_response = self.ai_model.generate_response(
                system_prompt=FORMATTED_ALLOCATION_PROMPT_SYSTEM, # Uses the module-level formatted system prompt
                user_content=user_content_for_allocation,
                temperature=AI_TEMPERATURE,
                max_tokens=AI_MAX_TOKENS
            )

            if not model_response or not model_response.content:
                cprint("❌ Failed to get a valid response from AI model for portfolio allocation.", "red")
                return None

            response_text = model_response.content.strip()
            allocations = self.parse_allocation_response(response_text)
            
            if not allocations:
                cprint("❌ Could not parse allocations from AI response.", "red")
                return None

            # Ensure USDC_ADDRESS is correctly keyed if AI used a placeholder
            for key in list(allocations.keys()): # Iterate over a copy of keys for safe modification
                if "USDC" in key.upper() and key != USDC_ADDRESS: # Check if a key contains USDC but is not the exact address
                    allocations[USDC_ADDRESS] = allocations.pop(key) # Standardize to the correct USDC_ADDRESS
                    cprint(f"ℹ️ Corrected USDC key from '{key}' to '{USDC_ADDRESS}' during allocation parsing.", "blue")
                    break

            # Validate and adjust allocations
            total_allocated_to_tokens = sum(v for k, v in allocations.items() if k != USDC_ADDRESS)

            # Ensure USDC is present in allocations, calculate if missing
            if USDC_ADDRESS not in allocations:
                usdc_amount = max(0, usd_size - total_allocated_to_tokens) # Ensure USDC is not negative
                allocations[USDC_ADDRESS] = usdc_amount
                cprint(f"ℹ️ Adding missing USDC allocation: ${usdc_amount:.2f}", "blue")
            else:
                # If AI allocates more than portfolio size, adjust USDC
                if total_allocated_to_tokens + allocations[USDC_ADDRESS] > usd_size:
                     new_usdc_amount = max(0, usd_size - total_allocated_to_tokens)
                     cprint(f"⚠️ AI allocated more than portfolio size. Original USDC: ${allocations[USDC_ADDRESS]:.2f}. Adjusted USDC to ${new_usdc_amount:.2f}", "yellow")
                     allocations[USDC_ADDRESS] = new_usdc_amount

            final_total_allocated = sum(allocations.values())
            # Allow a small deviation (e.g., 1%) for float precision issues
            if not (usd_size * 0.99 <= final_total_allocated <= usd_size * 1.01):
                cprint(f"❌ Final total allocation ${final_total_allocated:.2f} significantly differs from portfolio size ${usd_size:.2f}. Normalizing token allocations.", "red")
                
                usdc_value = allocations.get(USDC_ADDRESS, 0)
                target_token_sum = usd_size - usdc_value
                current_token_sum = sum(v for k,v in allocations.items() if k != USDC_ADDRESS)

                if current_token_sum > 0 and target_token_sum > 0: # Avoid division by zero and ensure target is positive
                    scaling_factor = target_token_sum / current_token_sum
                    for t_key in allocations:
                        if t_key != USDC_ADDRESS:
                            allocations[t_key] *= scaling_factor
                # Recalculate USDC after scaling tokens to ensure it sums up correctly
                allocations[USDC_ADDRESS] = usd_size - sum(v for k,v in allocations.items() if k != USDC_ADDRESS)


            min_cash_needed = usd_size * (CASH_PERCENTAGE / 100)
            if allocations.get(USDC_ADDRESS, 0) < min_cash_needed * 0.99: # Allow 1% leeway
                cprint(f"⚠️ AI allocation for USDC (${allocations.get(USDC_ADDRESS, 0):.2f}) is below minimum cash buffer (${min_cash_needed:.2f}). This may require review.", "yellow")

            cprint("\n📊 AI Recommended Portfolio Allocation (after validation & adjustments):", "green")
            for token, amount in allocations.items():
                token_display = "USDC" if token == USDC_ADDRESS else token
                cprint(f"  • {token_display}: ${amount:.2f}", "green")

            return allocations
            
        except Exception as e:
            cprint(f"❌ Error in AI portfolio allocation: {str(e)}", "red")
            return None

    def execute_allocations(self, allocation_dict):
        """Execute the allocations using AI entry for each position"""
        try:
            print("\n🚀 Moon Dev executing portfolio allocations...")
            
            for token, amount in allocation_dict.items():
                # Skip USDC and other excluded tokens
                if token in EXCLUDED_TOKENS:
                    print(f"💵 Keeping ${amount:.2f} in {token}")
                    continue
                    
                print(f"\n🎯 Processing allocation for {token}...")
                
                try:
                    # Get current position value
                    current_position = n.get_token_balance_usd(token)
                    target_allocation = amount
                    
                    print(f"🎯 Target allocation: ${target_allocation:.2f} USD")
                    print(f"📊 Current position: ${current_position:.2f} USD")
                    
                    if current_position < target_allocation:
                        print(f"✨ Executing entry for {token}")
                        n.ai_entry(token, amount)
                        print(f"✅ Entry complete for {token}")
                    else:
                        print(f"⏸️ Position already at target size for {token}")
                    
                except Exception as e:
                    print(f"❌ Error executing entry for {token}: {str(e)}")
                
                time.sleep(2)  # Small delay between entries
                
        except Exception as e:
            print(f"❌ Error executing allocations: {str(e)}")
            print("🔧 Moon Dev suggests checking the logs and trying again!")

    def handle_exits(self):
        """Check and exit positions based on SELL or NOTHING recommendations"""
        cprint("\n🔄 Checking for positions to exit...", "white", "on_blue")
        
        for _, row in self.recommendations_df.iterrows():
            token = row['token']
            
            # Skip excluded tokens (USDC and SOL)
            if token in EXCLUDED_TOKENS:
                continue
                
            action = row['action']
            
            # Check if we have a position
            current_position = n.get_token_balance_usd(token)
            
            if current_position > 0 and action in ["SELL", "NOTHING"]:
                cprint(f"\n🚫 AI Agent recommends {action} for {token}", "white", "on_yellow")
                cprint(f"💰 Current position: ${current_position:.2f}", "white", "on_blue")
                try:
                    cprint(f"📉 Closing position with chunk_kill...", "white", "on_cyan")
                    n.chunk_kill(token, max_usd_order_size, slippage)
                    cprint(f"✅ Successfully closed position", "white", "on_green")
                except Exception as e:
                    cprint(f"❌ Error closing position: {str(e)}", "white", "on_red")
            elif current_position > 0:
                cprint(f"✨ Keeping position for {token} (${current_position:.2f}) - AI recommends {action}", "white", "on_blue")

    def parse_allocation_response(self, response):
        """Parse the AI's allocation response and handle both string and TextBlock formats"""
        try:
            # Handle TextBlock format from Claude 3
            if isinstance(response, list):
                response = response[0].text if hasattr(response[0], 'text') else str(response[0])
            
            print("🔍 Raw response received:")
            print(response)
            
            # Find the JSON block between curly braces
            start = response.find('{')
            end = response.rfind('}') + 1
            if start == -1 or end == 0:
                raise ValueError("No JSON object found in response")
            
            json_str = response[start:end]
            
            # More aggressive JSON cleaning
            json_str = (json_str
                .replace('\n', '')          # Remove newlines
                .replace('    ', '')        # Remove indentation
                .replace('\t', '')          # Remove tabs
                .replace('\\n', '')         # Remove escaped newlines
                .replace(' ', '')           # Remove all spaces
                .strip())                   # Remove leading/trailing whitespace
            
            print("\n🧹 Cleaned JSON string:")
            print(json_str)
            
            # Parse the cleaned JSON
            allocations = json.loads(json_str)
            
            print("\n📊 Parsed allocations:")
            for token, amount in allocations.items():
                print(f"  • {token}: ${amount}")
            
            # Validate amounts are numbers
            for token, amount in allocations.items():
                if not isinstance(amount, (int, float)):
                    raise ValueError(f"Invalid amount type for {token}: {type(amount)}")
                if amount < 0:
                    raise ValueError(f"Negative allocation for {token}: {amount}")
            
            return allocations
            
        except Exception as e:
            print(f"❌ Error parsing allocation response: {str(e)}")
            print("🔍 Raw response:")
            print(response)
            return None

    def parse_portfolio_allocation(self, allocation_text):
        """Parse portfolio allocation from text response"""
        try:
            # Clean up the response text
            cleaned_text = allocation_text.strip()
            if "```json" in cleaned_text:
                # Extract JSON from code block if present
                json_str = cleaned_text.split("```json")[1].split("```")[0]
            else:
                # Find the JSON object between curly braces
                start = cleaned_text.find('{')
                end = cleaned_text.rfind('}') + 1
                json_str = cleaned_text[start:end]
            
            # Parse the JSON
            allocations = json.loads(json_str)
            
            print("📊 Parsed allocations:")
            for token, amount in allocations.items():
                print(f"  • {token}: ${amount}")
            
            return allocations
            
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing allocation JSON: {e}")
            print(f"🔍 Raw text received:\n{allocation_text}")
            return None
        except Exception as e:
            print(f"❌ Unexpected error parsing allocations: {e}")
            return None

    def run(self):
        """Run the trading agent (implements BaseAgent interface)"""
        self.run_trading_cycle()

    def run_trading_cycle(self, strategy_signals=None):
        """Run one complete trading cycle"""
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cprint(f"\n⏰ AI Agent Run Starting at {current_time}", "white", "on_green")
            
            # Collect OHLCV data for all tokens
            cprint("📊 Collecting market data...", "white", "on_blue")
            market_data = collect_all_tokens()
            
            # Analyze each token's data
            for token, data in market_data.items():
                cprint(f"\n🤖 AI Agent Analyzing Token: {token}", "white", "on_green")
                
                # Include strategy signals in analysis if available
                if strategy_signals and token in strategy_signals:
                    cprint(f"📊 Including {len(strategy_signals[token])} strategy signals in analysis", "cyan")
                    data['strategy_signals'] = strategy_signals[token]
                
                analysis = self.analyze_market_data(token, data)
                print(f"\n📈 Analysis for contract: {token}")
                print(analysis)
                print("\n" + "="*50 + "\n")
            
            # Show recommendations summary
            cprint("\n📊 Moon Dev's Trading Recommendations:", "white", "on_blue")
            summary_df = self.recommendations_df[['token', 'action', 'confidence']].copy()
            print(summary_df.to_string(index=False))
            
            # Handle exits first
            self.handle_exits()
            
            # Then proceed with new allocations
            cprint("\n💰 Calculating optimal portfolio allocation...", "white", "on_blue")
            allocation = self.allocate_portfolio()
            
            if allocation:
                cprint("\n💼 Moon Dev's Portfolio Allocation:", "white", "on_blue")
                print(json.dumps(allocation, indent=4))
                
                cprint("\n🎯 Executing allocations...", "white", "on_blue")
                self.execute_allocations(allocation)
                cprint("\n✨ All allocations executed!", "white", "on_blue")
            else:
                cprint("\n⚠️ No allocations to execute!", "white", "on_yellow")
            
            # Clean up temp data
            cprint("\n🧹 Cleaning up temporary data...", "white", "on_blue")
            try:
                for file in os.listdir('temp_data'):
                    if file.endswith('_latest.csv'):
                        os.remove(os.path.join('temp_data', file))
                cprint("✨ Temp data cleaned successfully!", "white", "on_green")
            except Exception as e:
                cprint(f"⚠️ Error cleaning temp data: {str(e)}", "white", "on_yellow")
            
        except Exception as e:
            cprint(f"\n❌ Error in trading cycle: {str(e)}", "white", "on_red")
            cprint("🔧 Moon Dev suggests checking the logs and trying again!", "white", "on_blue")

def main():
    """Main function to run the trading agent every 15 minutes"""
    cprint("🌙 Moon Dev AI Trading System Starting Up! 🚀", "white", "on_blue")
    
    agent = TradingAgent()
    INTERVAL = SLEEP_BETWEEN_RUNS_MINUTES * 60  # Convert minutes to seconds
    
    while True:
        try:
            agent.run_trading_cycle()
            
            next_run = datetime.now() + timedelta(minutes=SLEEP_BETWEEN_RUNS_MINUTES)
            cprint(f"\n⏳ AI Agent run complete. Next run at {next_run.strftime('%Y-%m-%d %H:%M:%S')}", "white", "on_green")
            
            # Sleep until next interval
            time.sleep(INTERVAL)
                
        except KeyboardInterrupt:
            cprint("\n👋 Moon Dev AI Agent shutting down gracefully...", "white", "on_blue")
            break
        except Exception as e:
            cprint(f"\n❌ Error: {str(e)}", "white", "on_red")
            cprint("🔧 Moon Dev suggests checking the logs and trying again!", "white", "on_blue")
            # Still sleep and continue on error
            time.sleep(INTERVAL)

if __name__ == "__main__":
    main() 