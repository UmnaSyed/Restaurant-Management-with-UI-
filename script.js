/* ============================================================
   DineHub — script.js
   Full backend integration with Flask REST API
   All API calls go through the BASE_URL constant below.
============================================================ */

const BASE_URL = 'http://127.0.0.1:5000/api';

/* ============================================================
   AUTH HELPERS
   Token is stored in localStorage after login.
   Every protected API call reads it from here.
============================================================ */
function getToken()           { return localStorage.getItem('dh_token'); }
function getUser()            { const u = localStorage.getItem('dh_user'); return u ? JSON.parse(u) : null; }
function setAuth(token, user) { localStorage.setItem('dh_token', token); localStorage.setItem('dh_user', JSON.stringify(user)); }
function clearAuth()          { localStorage.removeItem('dh_token'); localStorage.removeItem('dh_user'); }
function isLoggedIn()         { return !!getToken(); }

/* ============================================================
   API WRAPPER
   authFetch() — like fetch() but automatically adds the
   Authorization header so every protected route works.
============================================================ */
async function authFetch(endpoint, options = {}) {
    const token = getToken();
    const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}${endpoint}`, { ...options, headers });
    return res;
}

/* ============================================================
   SHOW TOAST NOTIFICATION
============================================================ */
function showToast(message, type = 'info') {
    let toast = document.getElementById('dh-toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'dh-toast';
        document.body.appendChild(toast);
    }
    toast.className = `dh-toast dh-toast--${type}`;
    toast.textContent = message;
    toast.style.opacity = '1';
    toast.style.transform = 'translateX(-50%) translateY(0)';
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(-50%) translateY(20px)';
    }, 3500);
}

/* ============================================================
   DOM READY — runs on BOTH home.html and index.html
============================================================ */
document.addEventListener('DOMContentLoaded', () => {

    // ── Render the nav auth button on every page ──
    renderNavAuth();

    // ── Page-specific logic ──
    const isOrderPage = document.body.classList.contains('order-page');
    if (isOrderPage) {
        initOrderPage();
    } else {
        initHomePage();
    }
});

/* ============================================================
   NAV AUTH BUTTON
   Shows "Login" when logged out, "Hi Name + Logout" when in.
   Injects into .nav-links on both pages.
============================================================ */
function renderNavAuth() {
    const navLinks = document.querySelector('.nav-links');
    if (!navLinks) return;

    // Remove any existing auth button so we don't duplicate
    const old = document.getElementById('nav-auth-btn');
    if (old) old.remove();

    const user = getUser();
    const btn  = document.createElement('button');
    btn.id     = 'nav-auth-btn';

    if (user) {
        btn.textContent = `Hi, ${user.name.split(' ')[0]}  ✕`;
        btn.title       = 'Click to logout';
        btn.className   = 'nav-auth-btn nav-auth-btn--out';
        btn.addEventListener('click', () => {
            clearAuth();
            showToast('Logged out successfully', 'info');
            renderNavAuth();
        });
    } else {
        btn.textContent = 'Login / Register';
        btn.className   = 'nav-auth-btn nav-auth-btn--in';
        btn.addEventListener('click', () => openAuthModal());
    }

    navLinks.appendChild(btn);
}

/* ============================================================
   AUTH MODAL
   Floating modal with Register and Login tabs.
   On success stores token + user and closes.
============================================================ */
function openAuthModal() {
    // Don't open twice
    if (document.getElementById('dh-auth-modal')) return;

    const overlay = document.createElement('div');
    overlay.id    = 'dh-auth-modal';
    overlay.innerHTML = `
        <div class="auth-modal-box">
            <button class="auth-close" id="authClose">✕</button>
            <div class="auth-tabs">
                <button class="auth-tab active" data-tab="login">Login</button>
                <button class="auth-tab" data-tab="register">Register</button>
            </div>

            <!-- LOGIN PANEL -->
            <div class="auth-panel" id="panel-login">
                <p class="auth-desc">Welcome back to DineHub.</p>
                <div class="auth-field">
                    <label>Email</label>
                    <input type="email" id="loginEmail" placeholder="you@example.com">
                </div>
                <div class="auth-field">
                    <label>Password</label>
                    <input type="password" id="loginPassword" placeholder="••••••••">
                </div>
                <button class="btn-primary full-width" id="loginSubmit">Login</button>
                <p class="auth-error hidden" id="loginError"></p>
            </div>

            <!-- REGISTER PANEL -->
            <div class="auth-panel hidden" id="panel-register">
                <p class="auth-desc">Create your DineHub account.</p>
                <div class="auth-field">
                    <label>Full Name</label>
                    <input type="text" id="regName" placeholder="Sara Ahmed">
                </div>
                <div class="auth-field">
                    <label>Email</label>
                    <input type="email" id="regEmail" placeholder="you@example.com">
                </div>
                <div class="auth-field">
                    <label>Phone (optional)</label>
                    <input type="tel" id="regPhone" placeholder="03001234567">
                </div>
                <div class="auth-field">
                    <label>Password</label>
                    <input type="password" id="regPassword" placeholder="••••••••">
                </div>
                <button class="btn-primary full-width" id="registerSubmit">Create Account</button>
                <p class="auth-error hidden" id="registerError"></p>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);

    // Close on overlay click or X button
    overlay.addEventListener('click', e => { if (e.target === overlay) closeAuthModal(); });
    document.getElementById('authClose').addEventListener('click', closeAuthModal);

    // Tab switching
    overlay.querySelectorAll('.auth-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            overlay.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
            overlay.querySelectorAll('.auth-panel').forEach(p => p.classList.add('hidden'));
            tab.classList.add('active');
            document.getElementById(`panel-${tab.dataset.tab}`).classList.remove('hidden');
        });
    });

    // LOGIN submit
    document.getElementById('loginSubmit').addEventListener('click', async () => {
        const email    = document.getElementById('loginEmail').value.trim();
        const password = document.getElementById('loginPassword').value;
        const errEl    = document.getElementById('loginError');
        errEl.classList.add('hidden');

        if (!email || !password) { showAuthError(errEl, 'Please fill in all fields.'); return; }

        const btn = document.getElementById('loginSubmit');
        btn.textContent = 'Logging in…';
        btn.disabled    = true;

        try {
            const res  = await fetch(`${BASE_URL}/auth/login`, {
                method:  'POST',
                headers: { 'Content-Type': 'application/json' },
                body:    JSON.stringify({ email, password, role: 'customer' })
            });
            const data = await res.json();

            if (!res.ok) { showAuthError(errEl, data.error || 'Login failed'); return; }

            setAuth(data.token, data.user);
            closeAuthModal();
            renderNavAuth();
            showToast(`Welcome back, ${data.user.name.split(' ')[0]}!`, 'success');

        } catch (err) {
            showAuthError(errEl, 'Could not reach server. Is Flask running?');
        } finally {
            btn.textContent = 'Login';
            btn.disabled    = false;
        }
    });

    // REGISTER submit
    document.getElementById('registerSubmit').addEventListener('click', async () => {
        const name     = document.getElementById('regName').value.trim();
        const email    = document.getElementById('regEmail').value.trim();
        const phone    = document.getElementById('regPhone').value.trim();
        const password = document.getElementById('regPassword').value;
        const errEl    = document.getElementById('registerError');
        errEl.classList.add('hidden');

        if (!name || !email || !password) { showAuthError(errEl, 'Name, email and password are required.'); return; }
        if (password.length < 6)          { showAuthError(errEl, 'Password must be at least 6 characters.'); return; }

        const btn = document.getElementById('registerSubmit');
        btn.textContent = 'Creating account…';
        btn.disabled    = true;

        try {
            const res  = await fetch(`${BASE_URL}/auth/register`, {
                method:  'POST',
                headers: { 'Content-Type': 'application/json' },
                body:    JSON.stringify({ name, email, phone, password })
            });
            const data = await res.json();

            if (!res.ok) { showAuthError(errEl, data.error || 'Registration failed'); return; }

            // Auto-login after register
            const loginRes  = await fetch(`${BASE_URL}/auth/login`, {
                method:  'POST',
                headers: { 'Content-Type': 'application/json' },
                body:    JSON.stringify({ email, password, role: 'customer' })
            });
            const loginData = await loginRes.json();

            if (loginRes.ok) {
                setAuth(loginData.token, loginData.user);
                closeAuthModal();
                renderNavAuth();
                showToast(`Account created! Welcome, ${loginData.user.name.split(' ')[0]}!`, 'success');
            } else {
                showAuthError(errEl, 'Account created — please login.');
            }

        } catch (err) {
            showAuthError(errEl, 'Could not reach server. Is Flask running?');
        } finally {
            btn.textContent = 'Create Account';
            btn.disabled    = false;
        }
    });
}

function closeAuthModal() {
    const m = document.getElementById('dh-auth-modal');
    if (m) m.remove();
}

function showAuthError(el, msg) {
    el.textContent = msg;
    el.classList.remove('hidden');
}

/* ============================================================
   HOME PAGE — home.html
   Handles: reservation form, walk-in form
============================================================ */
function initHomePage() {

    // ── RESERVATION FORM ──
    const reserveForm = document.getElementById('reserveForm');
    if (reserveForm) {
        reserveForm.addEventListener('submit', async function(e) {
            e.preventDefault();

            // Collect values — match the input order in the form
            const inputs    = reserveForm.querySelectorAll('input, select');
            const name      = inputs[0].value.trim();
            const phone     = inputs[1].value.trim();
            const dateTime  = inputs[2].value;           // datetime-local
            const partySel  = inputs[3].value;           // "2 people" etc.
            const partySize = parseInt(partySel);         // parse the number

            if (!name || !dateTime || !partySel || isNaN(partySize)) {
                showToast('Please fill in all reservation fields.', 'error');
                return;
            }

            // Must be logged in to reserve
            if (!isLoggedIn()) {
                showToast('Please login first to make a reservation.', 'error');
                openAuthModal();
                return;
            }

            const user = getUser();

            // Format datetime for the backend: "2025-07-15 19:30:00"
            const formattedDT = dateTime.replace('T', ' ') + ':00';

            const submitBtn = reserveForm.querySelector('button[type="submit"]');
            submitBtn.textContent = 'Requesting…';
            submitBtn.disabled    = true;

            try {
                const res  = await authFetch('/reservations/', {
                    method: 'POST',
                    body:   JSON.stringify({
                        customer_id: user.id,
                        party_size:  partySize,
                        date_time:   formattedDT
                    })
                });
                const data = await res.json();

                if (!res.ok) {
                    showToast(data.error || 'Could not make reservation.', 'error');
                    return;
                }

                // Show confirmation
                reserveForm.classList.add('hidden');
                const confirmEl = document.getElementById('reserveConfirm');
                confirmEl.classList.remove('hidden');

                // Update confirmation text with AI-assigned table info
                const msg = confirmEl.querySelector('p');
                if (msg && data.table_number) {
                    msg.textContent = `${data.ai_note} — Reservation #${data.reservation_id} confirmed for ${formattedDT.slice(0,16)}.`;
                }

                showToast(`Table ${data.table_number} reserved successfully!`, 'success');

            } catch (err) {
                showToast('Server error. Make sure Flask is running.', 'error');
            } finally {
                submitBtn.textContent = 'Request Reservation';
                submitBtn.disabled    = false;
            }
        });
    }

    // ── WALK-IN FORM ──
    // Walk-in doesn't hit the backend — it's a queue display only.
    // (Your backend has no walk-in table; it uses reservations for bookings.)
    let queueCount = 3;
    const walkinForm = document.getElementById('walkinForm');
    if (walkinForm) {
        walkinForm.addEventListener('submit', function(e) {
            e.preventDefault();
            queueCount++;
            const queueNumEl = document.getElementById('queueNumber');
            if (queueNumEl) queueNumEl.textContent = '#' + queueCount;
            walkinForm.classList.add('hidden');
            document.getElementById('walkinConfirm').classList.remove('hidden');
            showToast("You've been added to the queue!", 'success');
        });
    }
}

/* ============================================================
   ORDER PAGE — index.html
   Handles: order type toggle, cart, place order to backend
============================================================ */
function initOrderPage() {

    // ── STATE ──
    const cart = [];       // { name, price, qty, item_id }
    let   orderType = 'dine-in';

    // ── ORDER TYPE TOGGLE ──
    const btnDineIn      = document.getElementById('btnDineIn');
    const btnDelivery    = document.getElementById('btnDelivery');
    const dineinFields   = document.getElementById('dineinFields');
    const deliveryFields = document.getElementById('deliveryFields');
    const cartTypeBadge  = document.getElementById('cartTypeBadge');

    if (btnDineIn && btnDelivery) {
        btnDineIn.addEventListener('click', () => {
            orderType = 'dine-in';
            btnDineIn.classList.add('active');
            btnDelivery.classList.remove('active');
            dineinFields.classList.remove('hidden');
            deliveryFields.classList.add('hidden');
            if (cartTypeBadge) cartTypeBadge.textContent = '🍽️ Dine-In';
        });

        btnDelivery.addEventListener('click', () => {
            orderType = 'delivery';
            btnDelivery.classList.add('active');
            btnDineIn.classList.remove('active');
            deliveryFields.classList.remove('hidden');
            dineinFields.classList.add('hidden');
            if (cartTypeBadge) cartTypeBadge.textContent = '🛵 Delivery';
        });
    }

    // ── CART RENDERING ──
    function renderCart() {
        const container  = document.getElementById('cart-container');
        const subtotalEl = document.getElementById('subtotal');
        const taxEl      = document.getElementById('taxAmount');
        const totalEl    = document.getElementById('total-price');
        const totalsBox  = document.getElementById('cartTotals');
        const notesBox   = document.getElementById('cartNotes');

        if (!container) return;
        container.innerHTML = '';

        if (cart.length === 0) {
            container.innerHTML = `
                <div class="cart-empty">
                    <span>🛒</span>
                    <p>Your cart is empty.<br>Add items to get started.</p>
                </div>`;
            if (totalsBox) totalsBox.style.display = 'none';
            if (notesBox)  notesBox.style.display  = 'none';
            return;
        }

        cart.forEach((item, idx) => {
            const row = document.createElement('div');
            row.classList.add('cart-item-row');
            row.innerHTML = `
                <span class="cart-item-name">${item.name}</span>
                <div class="qty-control">
                    <button class="qty-btn" data-idx="${idx}" data-action="dec">−</button>
                    <span class="qty-num">${item.qty}</span>
                    <button class="qty-btn" data-idx="${idx}" data-action="inc">+</button>
                </div>
                <span class="cart-item-price">$${(item.price * item.qty).toFixed(2)}</span>
            `;
            container.appendChild(row);
        });

        // Quantity controls
        container.querySelectorAll('.qty-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const idx    = parseInt(btn.dataset.idx);
                const action = btn.dataset.action;
                if (action === 'inc') {
                    cart[idx].qty++;
                } else {
                    cart[idx].qty--;
                    if (cart[idx].qty <= 0) cart.splice(idx, 1);
                }
                renderCart();
            });
        });

        // Totals
        const subtotal = cart.reduce((s, i) => s + i.price * i.qty, 0);
        const tax      = subtotal * 0.10;
        const total    = subtotal + tax;

        if (subtotalEl) subtotalEl.textContent = `$${subtotal.toFixed(2)}`;
        if (taxEl)      taxEl.textContent      = `$${tax.toFixed(2)}`;
        if (totalEl)    totalEl.textContent    = `$${total.toFixed(2)}`;
        if (totalsBox)  totalsBox.style.display = 'block';
        if (notesBox)   notesBox.style.display  = 'block';
    }

    // ── ADD TO CART ──
    document.querySelectorAll('.add-to-cart').forEach(btn => {
        btn.addEventListener('click', () => {
            const card   = btn.closest('.menu-card');
            const name   = card.querySelector('h3').textContent.trim();
            const price  = parseFloat(card.getAttribute('data-price'));
            const itemId = parseInt(card.getAttribute('data-item-id'));

            const existing = cart.find(i => i.item_id === itemId);
            if (existing) {
                existing.qty++;
            } else {
                cart.push({ name, price, qty: 1, item_id: itemId });
            }

            btn.textContent = '✓ Added';
            btn.classList.add('added');
            setTimeout(() => { btn.textContent = '+ Add'; btn.classList.remove('added'); }, 1200);

            renderCart();
        });
    });

    // ── CLEAR CART ──
    const clearBtn = document.getElementById('clear-cart');
    if (clearBtn) {
        clearBtn.addEventListener('click', () => { cart.length = 0; renderCart(); });
    }

    // ── PLACE ORDER ──
    const confirmBtn       = document.getElementById('confirm-order');
    const cartActionsEl    = document.getElementById('cartActions');
    const orderConfirmedEl = document.getElementById('orderConfirmed');
    const orderSummaryText = document.getElementById('orderSummaryText');
    const orderIdEl        = document.getElementById('orderId');
    const cartTotalsEl     = document.getElementById('cartTotals');
    const cartNotesEl      = document.getElementById('cartNotes');

    if (confirmBtn) {
        confirmBtn.addEventListener('click', async () => {

            // ── Validation ──
            if (cart.length === 0) {
                showToast('Your cart is empty! Add items before placing an order.', 'error');
                return;
            }

            if (!isLoggedIn()) {
                showToast('Please login to place an order.', 'error');
                openAuthModal();
                return;
            }

            let tableId = null;
            let address = null;

            if (orderType === 'dine-in') {
                const tableSelect = document.getElementById('tableSelect');
                if (!tableSelect || !tableSelect.value) {
                    showToast('Please select a table for dine-in.', 'error');
                    return;
                }
                tableId = parseInt(tableSelect.value);
            }

            if (orderType === 'delivery') {
                const addrInput = document.getElementById('deliveryAddress');
                if (!addrInput || !addrInput.value.trim()) {
                    showToast('Please enter a delivery address.', 'error');
                    return;
                }
                address = addrInput.value.trim();
            }

            const user        = getUser();
            const specialNote = document.getElementById('specialNote')?.value.trim() || '';

            // Build items array for the backend
            const items = cart.map(i => ({
                item_id:      i.item_id,
                quantity:     i.qty,
                special_note: specialNote || undefined
            }));

            // Build request body
            const body = {
                customer_id: user.id,
                order_type:  orderType,
                items
            };
            if (tableId) body.table_id = tableId;

            confirmBtn.textContent = 'Placing order…';
            confirmBtn.disabled    = true;

            try {
                // ── Step 1: Place the order ──
                const res  = await authFetch('/orders/', {
                    method: 'POST',
                    body:   JSON.stringify(body)
                });
                const data = await res.json();

                if (!res.ok) {
                    showToast(data.error || 'Failed to place order.', 'error');
                    return;
                }

                const orderId = data.order_id;

                // ── Step 2: If delivery, assign a rider ──
                if (orderType === 'delivery' && address) {
                    await authFetch(`/deliveries/assign/${orderId}`, {
                        method: 'POST',
                        body:   JSON.stringify({ address })
                    });
                    // We don't block on this — even if no rider is available,
                    // the order is still placed successfully.
                }

                // ── Step 3: Show confirmation ──
                const subtotal = cart.reduce((s, i) => s + i.price * i.qty, 0);
                const total    = (subtotal * 1.10).toFixed(2);

                if (orderIdEl)        orderIdEl.textContent        = orderId;
                if (orderSummaryText) orderSummaryText.textContent =
                    `${orderType === 'dine-in' ? 'Dine-In' : 'Delivery'} order — $${total} total. ` +
                    (orderType === 'delivery'
                        ? 'A rider has been assigned and is on the way!'
                        : 'Food is being prepared at your table!') +
                    ` Priority: ${data.priority}${data.is_peak ? ' (peak hour — fast track!)' : ''}`;

                cart.length = 0;

                const cartItemsList = document.getElementById('cart-container');
                if (cartItemsList)  cartItemsList.style.display  = 'none';
                if (cartTotalsEl)   cartTotalsEl.style.display   = 'none';
                if (cartNotesEl)    cartNotesEl.style.display    = 'none';
                if (cartActionsEl)  cartActionsEl.style.display  = 'none';
                if (orderConfirmedEl) orderConfirmedEl.classList.remove('hidden');

                showToast(`Order #${orderId} placed successfully!`, 'success');

            } catch (err) {
                showToast('Server error. Make sure Flask is running.', 'error');
            } finally {
                confirmBtn.textContent = 'Place Order';
                confirmBtn.disabled    = false;
            }
        });
    }

    renderCart();
}