#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import io
import random
import string
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
import qrcode

import config
from database import *

# ====================
# LOGGING SETUP
# ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ====================
# CONVERSATION STATES
# ====================
ADDING_IDS = 1

# ====================
# HELPER FUNCTIONS
# ====================
def generate_order_id():
    """Unique order ID generate karta hai"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    random_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"ORD{timestamp}{random_chars}"

def generate_qr_code(data):
    """QR code generate karta hai"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    bio = io.BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    
    return bio

def is_admin(user_id):
    """Check if user is admin"""
    return user_id == config.ADMIN_ID

# ====================
# START COMMAND
# ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    
    welcome_text = f"""
👋 **Welcome, {username}!**

🤖 **Premium ID Store Bot**

🛍️ **Features:**
• Premium IDs Purchase
• Instant Delivery
• Secure Payments
• 24/7 Support

⚡ **Commands:**
/start - Start Bot
/buy - Buy ID
/myorders - My Orders
/help - Help

📞 **Support:** {config.SUPPORT_USERNAME}
    """
    
    keyboard = [
        [InlineKeyboardButton("🛒 Buy ID", callback_data='buy_id')],
        [InlineKeyboardButton("📦 My Orders", callback_data='my_orders')],
        [InlineKeyboardButton("📞 Support", url='https://t.me/maarjauky')]
    ]
    
    if is_admin(user_id):
        keyboard.append([InlineKeyboardButton("👑 Admin Panel", callback_data='admin_panel')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# ====================
# BUY FLOW
# ====================
async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buy command handler"""
    products = get_available_products()
    
    if not products:
        await update.message.reply_text(
            "❌ **Currently no IDs available!**\n\n"
            "Please check back later or contact admin."
        )
        return
    
    keyboard = []
    for product in products:
        product_id, product_data, category, price = product
        button_text = f"{category} - ₹{price}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f'select_{product_id}')])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='back_to_main')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🛒 **Available IDs:**\n\n"
        "Select a category to purchase:",
        reply_markup=reply_markup
    )

async def select_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Product selection handler"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    product_id = int(data.split('_')[1])
    
    product = get_product_by_id(product_id)
    
    if not product:
        await query.edit_message_text("❌ This product is no longer available!")
        return
    
    pid, product_data, category, price, sold, added_date = product
    
    if sold == 1:
        await query.edit_message_text("❌ This ID has already been sold!")
        return
    
    # Store in context
    context.user_data['selected_product_id'] = pid
    context.user_data['selected_product_data'] = product_data
    context.user_data['selected_price'] = price
    context.user_data['selected_category'] = category
    
    keyboard = [
        [InlineKeyboardButton("✅ Confirm Purchase", callback_data='confirm_purchase')],
        [InlineKeyboardButton("❌ Cancel", callback_data='cancel_purchase')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📋 **Order Summary:**\n\n"
        f"🏷️ **Category:** {category}\n"
        f"💰 **Price:** ₹{price}\n\n"
        f"**Confirm purchase?**\n\n"
        f"_After confirmation, you will get payment QR code._",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def confirm_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Purchase confirmation handler"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    
    # Get product details from context
    product_id = context.user_data.get('selected_product_id')
    product_data = context.user_data.get('selected_product_data')
    price = context.user_data.get('selected_price', config.DEFAULT_PRICE)
    category = context.user_data.get('selected_category', 'General')
    
    if not product_id:
        await query.edit_message_text("❌ Session expired. Please start again.")
        return
    
    # Generate order ID
    order_id = generate_order_id()
    
    # Create order in database
    create_order(order_id, user_id, username, product_id, product_data, price)
    
    # Generate payment QR
    payment_note = f"Order {order_id} - {username}"
    qr_data = f"upi://pay?pa={config.UPI_ID}&pn={config.UPI_NAME}&am={price}&tn={payment_note}"
    
    qr_image = generate_qr_code(qr_data)
    
    # Store order_id in context
    context.user_data['current_order_id'] = order_id
    
    # Send payment instructions
    payment_text = f"""
💰 **Payment Instructions**

🆔 **Order ID:** `{order_id}`
👤 **Customer:** {username}
📦 **Product:** {category}
💳 **Amount:** ₹{price}
📱 **UPI ID:** `{config.UPI_ID}`

**📋 IMPORTANT:**
1. Scan QR code or send payment to UPI ID
2. **Payment notes mein yeh Order ID zaroor add karein:**
   `{order_id}`
3. Payment complete hone ke baad screenshot yahan send karein

⏰ **Payment Time:** {config.PAYMENT_TIMEOUT_MINUTES} minutes
📞 **Support:** {config.SUPPORT_USERNAME}
    """
    
    await query.edit_message_text(
        payment_text,
        parse_mode='Markdown'
    )
    
    # Send QR code
    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=qr_image,
        caption="📱 Scan QR code to pay"
    )

# ====================
# PAYMENT SCREENSHOT HANDLER
# ====================
async def handle_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Payment screenshot handler"""
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    
    # Check if user has pending order
    order = get_order_by_user(user_id)
    
    if not order:
        await update.message.reply_text(
            "❌ **No pending order found!**\n\n"
            "Please start a new order using /buy"
        )
        return
    
    order_id = order[0]
    
    if order[7] != 'pending':  # status
        await update.message.reply_text(
            "❌ **Payment already submitted!**\n\n"
            "Please wait for admin approval."
        )
        return
    
    # Get the highest resolution photo
    photo = update.message.photo[-1]
    file_id = photo.file_id
    
    # Update order with screenshot
    update_order_screenshot(order_id, file_id)
    
    # Notify admin
    admin_message = f"""
🆕 **New Payment Pending!**

👤 **User:** @{username}
🆔 **User ID:** `{user_id}`
💰 **Amount:** ₹{order[5]}
🆔 **Order ID:** `{order_id}`
📦 **Product:** {order[4]}
📅 **Time:** {order[8]}

**Quick Actions:**
✅ Approve: `/approve_{order_id}`
❌ Reject: `/reject_{order_id}`
    """
    
    try:
        # Send notification to admin
        await context.bot.send_message(
            chat_id=config.ADMIN_ID,
            text=admin_message,
            parse_mode='Markdown'
        )
        
        # Forward screenshot to admin
        await context.bot.send_photo(
            chat_id=config.ADMIN_ID,
            photo=file_id,
            caption=f"Payment screenshot for order {order_id}"
        )
        
        # Confirm to user
        await update.message.reply_text(
            "✅ **Payment screenshot received!**\n\n"
            "Admin verification in progress...\n"
            "You will receive your ID shortly.\n\n"
            "⏳ Usually takes 5-10 minutes.\n"
            f"📞 Contact: {config.SUPPORT_USERNAME}"
        )
        
    except Exception as e:
        logger.error(f"Error notifying admin: {e}")
        await update.message.reply_text(
            "⚠️ **Screenshot received but admin notification failed!**\n\n"
            f"Please contact admin directly: {config.SUPPORT_USERNAME}"
        )

# ====================
# ADMIN COMMANDS
# ====================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin panel"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Access denied!")
        return
    
    keyboard = [
        [InlineKeyboardButton("➕ Add IDs", callback_data='add_ids_admin'),
         InlineKeyboardButton("📦 View IDs", callback_data='view_ids_admin')],
        [InlineKeyboardButton("⏳ Pending Orders", callback_data='pending_orders'),
         InlineKeyboardButton("📊 Statistics", callback_data='stats_admin')],
        [InlineKeyboardButton("👥 Users", callback_data='users_list')],
        [InlineKeyboardButton("🔙 Main Menu", callback_data='back_to_main')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "👑 **Admin Panel**\n\n"
        "Select an option:",
        reply_markup=reply_markup
    )

async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin start command"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Access denied!")
        return
    
    keyboard = [
        [InlineKeyboardButton("➕ Add IDs", callback_data='add_ids_admin'),
         InlineKeyboardButton("📦 View IDs", callback_data='view_ids_admin')],
        [InlineKeyboardButton("⏳ Pending Orders", callback_data='pending_orders'),
         InlineKeyboardButton("📊 Statistics", callback_data='stats_admin')],
        [InlineKeyboardButton("🔙 Main Menu", callback_data='back_to_main')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👑 **Admin Panel**\n\n"
        "Select an option:",
        reply_markup=reply_markup
    )

async def add_ids_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add IDs command"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Access denied!")
        return
    
    await update.message.reply_text(
        "📝 **Add IDs in this format:**\n\n"
        "`ID_PASSWORD,Category,Price`\n\n"
        "**Example:**\n"
        "`username:password123,Netflix,50`\n"
        "`email@gmail.com:pass456,Disney+,75`\n"
        "`user:pass,Prime Video,60`\n\n"
        "Send multiple lines for multiple IDs.\n\n"
        "Type /cancel to cancel."
    )
    
    return ADDING_IDS

async def handle_add_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle IDs input"""
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    
    text = update.message.text
    lines = text.strip().split('\n')
    
    added_count = 0
    duplicate_count = 0
    error_count = 0
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        try:
            parts = line.split(',')
            if len(parts) >= 1:
                product_data = parts[0].strip()
                category = parts[1].strip() if len(parts) > 1 else "General"
                price = int(parts[2].strip()) if len(parts) > 2 else config.DEFAULT_PRICE
                
                if add_product(product_data, category, price):
                    added_count += 1
                else:
                    duplicate_count += 1
        except ValueError:
            error_count += 1
        except Exception as e:
            error_count += 1
            logger.error(f"Error adding ID: {e}")
    
    report = f"""
✅ **IDs Added Successfully!**

📊 **Report:**
• ✅ Added: {added_count}
• ⚠️ Duplicate: {duplicate_count}
• ❌ Errors: {error_count}
• 📄 Total lines: {len(lines)}

View all IDs: /viewids
    """
    
    await update.message.reply_text(report)
    
    return ConversationHandler.END

async def view_ids_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View all IDs"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Access denied!")
        return
    
    products = get_available_products()
    
    if not products:
        await update.message.reply_text("📭 No IDs available!")
        return
    
    message = "📋 **Available IDs:**\n\n"
    
    for idx, product in enumerate(products, 1):
        product_id, product_data, category, price = product
        display_data = product_data[:25] + "..." if len(product_data) > 25 else product_data
        message += f"{idx}. {category} - ₹{price}\n"
        message += f"   ID: `{display_data}`\n"
        message += f"   DB ID: {product_id}\n\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def pending_orders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View pending orders"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Access denied!")
        return
    
    orders = get_pending_orders()
    
    if not orders:
        await update.message.reply_text("✅ No pending orders!")
        return
    
    message = "⏳ **Pending Orders:**\n\n"
    
    for order in orders:
        order_id, user_id, username, product_id, product_data, amount, screenshot_id, status, order_date, admin_date, admin_id = order
        
        message += f"🆔 **Order:** `{order_id}`\n"
        message += f"👤 **User:** @{username} (`{user_id}`)\n"
        message += f"💰 **Amount:** ₹{amount}\n"
        message += f"📅 **Time:** {order_date}\n"
        message += f"✅ **Approve:** `/approve_{order_id}`\n"
        message += f"❌ **Reject:** `/reject_{order_id}`\n"
        message += "─" * 30 + "\n\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def approve_order_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Approve order manually"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Access denied!")
        return
    
    command = update.message.text
    order_id = command.replace('/approve_', '').strip()
    
    order = get_order_by_id(order_id)
    
    if not order:
        await update.message.reply_text(f"❌ Order `{order_id}` not found!", parse_mode='Markdown')
        return
    
    if order[7] != 'waiting_approval':
        await update.message.reply_text(
            f"❌ Order `{order_id}` is already {order[7]}!",
            parse_mode='Markdown'
        )
        return
    
    # Get product to deliver
    product_id = order[3]
    product = get_product_by_id(product_id)
    
    if not product:
        await update.message.reply_text(
            f"❌ Product not found for order `{order_id}`!",
            parse_mode='Markdown'
        )
        return
    
    product_data = product[1]
    category = product[2]
    price = product[3]
    
    # Approve order
    approve_order(order_id, update.effective_user.id)
    
    # Send product to customer
    try:
        delivery_message = f"""
✅ **Payment Verified Successfully!**

🎉 **Your Purchased ID:**

`{product_data}`

📦 **Category:** {category}
💰 **Amount Paid:** ₹{price}
🆔 **Order ID:** `{order_id}`
📅 **Delivery Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📋 **Instructions:**
1. Use these credentials to login
2. Change password if possible
3. Enjoy the service!

🛡️ **Note:** This is a digital product.

📞 **Support:** {config.SUPPORT_USERNAME}

Thank you for your purchase! 🙏
"""
        
        await context.bot.send_message(
            chat_id=order[1],  # user_id
            text=delivery_message,
            parse_mode='Markdown'
        )
        
        await update.message.reply_text(
            f"✅ Order `{order_id}` approved and delivered to user!",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error delivering product: {e}")
        await update.message.reply_text(
            f"⚠️ Order approved but delivery failed: {e}"
        )

async def reject_order_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reject order"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Access denied!")
        return
    
    command = update.message.text
    order_id = command.replace('/reject_', '').strip()
    
    order = get_order_by_id(order_id)
    
    if not order:
        await update.message.reply_text(f"❌ Order `{order_id}` not found!", parse_mode='Markdown')
        return
    
    # Reject order
    reject_order(order_id, update.effective_user.id)
    
    # Notify user
    try:
        await context.bot.send_message(
            chat_id=order[1],  # user_id
            text=f"❌ **Order Rejected**\n\n"
                 f"Your order `{order_id}` has been rejected by admin.\n\n"
                 f"**Possible reasons:**\n"
                 f"• Invalid payment screenshot\n"
                 f"• Payment not received\n"
                 f"• Wrong amount\n\n"
                 f"Please contact admin for more details.\n"
                 f"📞 {config.SUPPORT_USERNAME}"
        )
    except Exception as e:
        logger.error(f"Error notifying user: {e}")
    
    await update.message.reply_text(
        f"❌ Order `{order_id}` rejected! User notified.",
        parse_mode='Markdown'
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot statistics"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Access denied!")
        return
    
    stats = get_stats()
    
    message = f"""
📊 **Bot Statistics**

📦 **Products:**
• Total: {stats['total_products']}
• Available: {stats['available_products']}
• Sold: {stats['sold_products']}

💰 **Orders:**
• Total: {stats['total_orders']}
• Approved: {stats['approved_orders']}
• Pending: {stats['pending_orders']}

💵 **Revenue:** ₹{stats['total_revenue']}

👥 **Users:** {stats['total_users']}

🔄 **Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    await update.message.reply_text(message)

async def view_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View all users"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Access denied!")
        return
    
    users = get_all_users()
    
    if not users:
        await update.mess