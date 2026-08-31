import React, { useEffect, useMemo, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE || (import.meta.env.DEV ? "http://localhost:8000" : "");
const sessionKey = "inventory-session-token";

const nav = [
  ["erp", "ERP", "ER"],
  ["ai-advisor", "AI Advisor", "AI"],
  ["dashboard", "GRN", "GR"],
  ["invoices", "Invoices", "IV"],
  ["process", "Process", "PR"],
  ["machining", "Machining", "MC"],
  ["cnc-machines", "CNC Machines", "CN"],
  ["salary", "Salary", "SA"],
  ["workers", "Workers", "WK"],
  ["profile", "Profile", "PF"]
];

const emptyAuth = { companyName: "", address: "", name: "", phone: "", email: "", password: "", role: "manager", identity: "" };

const helpLanguages = [
  ["en", "English"],
  ["hi", "Hindi"],
  ["ta", "Tamil"],
  ["te", "Telugu"],
  ["kn", "Kannada"],
  ["ml", "Malayalam"]
];

const helpText = {
  en: {
    greeting: "Ask me about GRN, heat numbers, process, machining, CNC machines, invoices, purchase orders, users, salary, or AI order suggestions.",
    grn: "To enter GRN, open GRN, fill date, time, drawing, material, HS code, quantity, rate, customer, and one heat number per part. Then save the GRN.",
    heat: "Heat numbers must be entered one per line. If quantity is 5, enter 5 heat numbers. You can search invoices later using any heat number.",
    process: "Use Process to approve or reject incoming material. Approved material moves to Machining. Rejected material creates rejected-document data.",
    machining: "Use Machining to assign a CNC machine, enter raw material heat number, save the CNC document, and complete machining when work is done.",
    cnc: "Use CNC Machines to add an MTConnect Agent URL. The app reads live status from the machine using the MTConnect /current endpoint.",
    invoice: "Use Invoice Search to find documents by heat number. Incoming GRN invoices, CNC machining documents, outgoing invoices, and not OK invoices are shown as files.",
    po: "Use Purchase Orders to save drawing number, company name, production rate, inward rate, and final rate. AI Advisor uses this for profit prediction.",
    ai: "Use AI Advisor to run the local model. It ranks items by profit, demand, quality score, repeat orders, and rejection risk.",
    user: "Owners can approve managers and employees in Requests. Managers can work with employees but cannot approve manager requests.",
    salary: "Use Salary to choose an employee, enter rate per hour, in time, and out time. The system calculates and saves salary.",
    fallback: "I can help with GRN, heat number, process, machining, CNC, invoices, purchase orders, AI Advisor, users, and salary. Ask about one of these topics."
  },
  hi: {
    greeting: "आप GRN, heat number, process, machining, CNC, invoice, purchase order, users, salary, या AI सुझावों के बारे में पूछ सकते हैं.",
    grn: "GRN डालने के लिए GRN मेनू खोलें, date, time, drawing, material, HS code, quantity, rate, customer और हर part का heat number भरें.",
    heat: "Heat number हर line में एक डालें. Quantity 5 है तो 5 heat numbers डालें. बाद में heat number से invoice search कर सकते हैं.",
    process: "Process में incoming material को OK या reject करें. OK material Machining में जाएगा.",
    machining: "Machining में CNC machine चुनें, raw material heat number डालें, CNC document save करें, फिर work complete होने पर machining complete करें.",
    cnc: "CNC Machines में MTConnect Agent URL जोड़ें. App machine का live status MTConnect /current से पढ़ता है.",
    invoice: "Invoice Search में heat number डालकर related documents देख सकते हैं.",
    po: "Purchase Orders में drawing, company, production rate, inward rate और final rate save करें. AI profit prediction में इसे use करता है.",
    ai: "AI Advisor profit, demand, quality, repeat orders और rejection risk के आधार पर suggestions देता है.",
    user: "Owner Requests में managers और employees को approve कर सकता है.",
    salary: "Salary में employee, hourly rate, in time और out time डालें. System salary calculate करेगा.",
    fallback: "मैं GRN, heat number, process, machining, CNC, invoice, purchase order, AI Advisor, users और salary में मदद कर सकता हूँ."
  },
  ta: {
    greeting: "GRN, heat number, process, machining, CNC, invoice, purchase order, users, salary, AI suggestions பற்றி கேட்கலாம்.",
    grn: "GRN பதிவு செய்ய GRN menu திறந்து date, time, drawing, material, HS code, quantity, rate, customer மற்றும் ஒவ்வொரு part க்கும் heat number உள்ளிடவும்.",
    heat: "Heat number ஒவ்வொரு line லும் ஒன்று. Quantity 5 என்றால் 5 heat numbers வேண்டும். பின்னர் heat number மூலம் invoice search செய்யலாம்.",
    process: "Process பகுதியில் material ஐ OK அல்லது reject செய்யலாம். OK material Machining க்கு செல்லும்.",
    machining: "Machining பகுதியில் CNC machine தேர்வு செய்து, raw material heat number உள்ளிட்டு, CNC document save செய்து, பிறகு machining complete செய்யவும்.",
    cnc: "CNC Machines பகுதியில் MTConnect Agent URL சேர்க்கவும். App /current endpoint மூலம் live status படிக்கும்.",
    invoice: "Invoice Search பகுதியில் heat number மூலம் documents காணலாம்.",
    po: "Purchase Orders பகுதியில் drawing, company, production rate, inward rate, final rate save செய்யவும். AI இதை profit prediction க்கு பயன்படுத்தும்.",
    ai: "AI Advisor profit, demand, quality, repeat orders, rejection risk அடிப்படையில் suggestions தரும்.",
    user: "Owner Requests பகுதியில் managers மற்றும் employees approve செய்யலாம்.",
    salary: "Salary பகுதியில் employee, hourly rate, in time, out time உள்ளிடவும். System salary கணக்கிடும்.",
    fallback: "GRN, heat number, process, machining, CNC, invoice, purchase order, AI Advisor, users, salary பற்றி உதவ முடியும்."
  },
  te: {
    greeting: "GRN, heat number, process, machining, CNC, invoice, purchase order, users, salary, AI suggestions గురించి అడగండి.",
    grn: "GRN కోసం date, time, drawing, material, HS code, quantity, rate, customer మరియు ప్రతి part heat number నమోదు చేయండి.",
    heat: "ప్రతి line లో ఒక heat number ఇవ్వండి. Quantity 5 అయితే 5 heat numbers ఇవ్వాలి.",
    process: "Process లో material OK లేదా reject చేయండి. OK material Machining కు వెళ్తుంది.",
    machining: "Machining లో CNC machine ఎంచుకుని heat number నమోదు చేసి CNC document save చేసి తర్వాత machining complete చేయండి.",
    cnc: "CNC Machines లో MTConnect Agent URL జోడించండి. App /current ద్వారా live status చదువుతుంది.",
    invoice: "Invoice Search లో heat number ద్వారా documents చూడవచ్చు.",
    po: "Purchase Orders లో drawing, company, rates save చేయండి. AI profit prediction కోసం ఉపయోగిస్తుంది.",
    ai: "AI Advisor profit, demand, quality, repeat orders, rejection risk ఆధారంగా suggestions ఇస్తుంది.",
    user: "Owner Requests లో managers మరియు employees approve చేయవచ్చు.",
    salary: "Salary లో employee, hourly rate, in time, out time ఇవ్వండి. System salary calculate చేస్తుంది.",
    fallback: "GRN, heat number, process, machining, CNC, invoice, purchase order, AI Advisor, users, salary గురించి సహాయం చేయగలను."
  },
  kn: {
    greeting: "GRN, heat number, process, machining, CNC, invoice, purchase order, users, salary, AI suggestions ಬಗ್ಗೆ ಕೇಳಿ.",
    grn: "GRN ಗೆ date, time, drawing, material, HS code, quantity, rate, customer ಮತ್ತು ಪ್ರತಿ part heat number ನಮೂದಿಸಿ.",
    heat: "ಪ್ರತಿ line ನಲ್ಲಿ ಒಂದು heat number ಹಾಕಿ. Quantity 5 ಇದ್ದರೆ 5 heat numbers ಬೇಕು.",
    process: "Process ನಲ್ಲಿ material OK ಅಥವಾ reject ಮಾಡಿ. OK material Machining ಗೆ ಹೋಗುತ್ತದೆ.",
    machining: "Machining ನಲ್ಲಿ CNC machine ಆಯ್ಕೆ ಮಾಡಿ, heat number ಹಾಕಿ, CNC document save ಮಾಡಿ, ನಂತರ machining complete ಮಾಡಿ.",
    cnc: "CNC Machines ನಲ್ಲಿ MTConnect Agent URL ಸೇರಿಸಿ. App /current ಮೂಲಕ live status ಓದುತ್ತದೆ.",
    invoice: "Invoice Search ನಲ್ಲಿ heat number ಮೂಲಕ documents ನೋಡಬಹುದು.",
    po: "Purchase Orders ನಲ್ಲಿ drawing, company, rates save ಮಾಡಿ. AI profit prediction ಗೆ ಬಳಸುತ್ತದೆ.",
    ai: "AI Advisor profit, demand, quality, repeat orders, rejection risk ಆಧಾರದಲ್ಲಿ suggestions ಕೊಡುತ್ತದೆ.",
    user: "Owner Requests ನಲ್ಲಿ managers ಮತ್ತು employees approve ಮಾಡಬಹುದು.",
    salary: "Salary ನಲ್ಲಿ employee, hourly rate, in time, out time ಹಾಕಿ. System salary calculate ಮಾಡುತ್ತದೆ.",
    fallback: "GRN, heat number, process, machining, CNC, invoice, purchase order, AI Advisor, users, salary ಬಗ್ಗೆ ಸಹಾಯ ಮಾಡಬಹುದು."
  },
  ml: {
    greeting: "GRN, heat number, process, machining, CNC, invoice, purchase order, users, salary, AI suggestions എന്നിവയെക്കുറിച്ച് ചോദിക്കാം.",
    grn: "GRN നായി date, time, drawing, material, HS code, quantity, rate, customer, ഓരോ part ന്റെയും heat number നൽകുക.",
    heat: "ഓരോ line ലും ഒരു heat number നൽകുക. Quantity 5 ആണെങ്കിൽ 5 heat numbers വേണം.",
    process: "Process ൽ material OK അല്ലെങ്കിൽ reject ചെയ്യുക. OK material Machining ലേക്ക് പോകും.",
    machining: "Machining ൽ CNC machine തിരഞ്ഞെടുക്കുക, heat number നൽകുക, CNC document save ചെയ്യുക, പിന്നെ machining complete ചെയ്യുക.",
    cnc: "CNC Machines ൽ MTConnect Agent URL ചേർക്കുക. App /current വഴി live status വായിക്കും.",
    invoice: "Invoice Search ൽ heat number ഉപയോഗിച്ച് documents കാണാം.",
    po: "Purchase Orders ൽ drawing, company, rates save ചെയ്യുക. AI profit prediction ന് ഉപയോഗിക്കും.",
    ai: "AI Advisor profit, demand, quality, repeat orders, rejection risk അടിസ്ഥാനമാക്കി suggestions നൽകും.",
    user: "Owner Requests ൽ managers ഉം employees ഉം approve ചെയ്യാം.",
    salary: "Salary ൽ employee, hourly rate, in time, out time നൽകുക. System salary calculate ചെയ്യും.",
    fallback: "GRN, heat number, process, machining, CNC, invoice, purchase order, AI Advisor, users, salary എന്നിവയിൽ സഹായിക്കാം."
  }
};

function App() {
  const [token, setToken] = useState(localStorage.getItem(sessionKey) || "");
  const [user, setUser] = useState(null);
  const [authTab, setAuthTab] = useState("login");
  const [auth, setAuth] = useState(emptyAuth);
  const [view, setView] = useState("dashboard");
  const [message, setMessage] = useState("");
  const [dashboard, setDashboard] = useState(null);
  const [erp, setErp] = useState(null);
  const [users, setUsers] = useState([]);
  const [search, setSearch] = useState("");

  const api = useMemo(() => ({
    async request(path, options = {}) {
      const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
      if (token) headers.Authorization = `Bearer ${token}`;
      const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || data.error || "Something went wrong.");
      return data;
    },
    get(path) { return this.request(path); },
    post(path, body) { return this.request(path, { method: "POST", body: JSON.stringify(body) }); },
    patch(path, body) { return this.request(path, { method: "PATCH", body: JSON.stringify(body) }); }
  }), [token]);

  async function refresh() {
    if (!token) return;
    try {
      const me = await api.get("/api/me");
      setUser(me.user);
      if (me.user.role === "owner" || me.user.role === "manager") {
        const [dash, people, erpData] = await Promise.all([api.get("/api/dashboard"), api.get("/api/users"), api.get("/api/erp/overview")]);
        setDashboard(dash);
        setUsers(people.users);
        setErp(erpData);
      }
    } catch (error) {
      if (error.message === "Please log in." || error.message === "Session expired. Please log in again.") {
        localStorage.removeItem(sessionKey);
        setToken("");
        setUser(null);
      }
      setMessage(error.message);
    }
  }

  useEffect(() => { refresh(); }, [token]);

  async function submitAuth(event) {
    event.preventDefault();
    try {
      const path = authTab === "owner" ? "/api/auth/owner-register" : authTab === "staff" ? "/api/auth/staff-register" : "/api/auth/login";
      const data = await api.post(path, auth);
      if (data.token) {
        localStorage.setItem(sessionKey, data.token);
        setToken(data.token);
        setUser(data.user);
        setMessage("Logged in.");
      } else {
        setMessage(data.message);
        setAuthTab("login");
      }
    } catch (error) {
      setMessage(error.message);
    }
  }

  async function logout() {
    await api.post("/api/auth/logout", {}).catch(() => {});
    localStorage.removeItem(sessionKey);
    setToken("");
    setUser(null);
  }

  if (!token || !user) {
    return <AuthScreen auth={auth} setAuth={setAuth} authTab={authTab} setAuthTab={setAuthTab} submit={submitAuth} message={message} />;
  }

  const allowedNav = nav.filter(([id]) => {
    if (user.role === "employee") return ["profile"].includes(id);
    if (user.role === "manager") return !["requests", "managers"].includes(id);
    return true;
  });

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <span className="brand-mark">ERP</span>
          <p className="eyebrow">Enterprise ERP</p>
          <h1>{dashboard?.company?.name || user.companyName}</h1>
        </div>
        <nav>
          {allowedNav.map(([id, label, code]) => <button key={id} className={view === id ? "active" : ""} onClick={() => setView(id)}><span>{code}</span>{label}</button>)}
        </nav>
        <div className="sidebar-footer">
          <small>{user.name}</small>
          <button className="btn secondary" onClick={logout}>Logout</button>
        </div>
      </aside>
      <main className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">{user.role}</p>
            <h2>{viewTitle(view)}</h2>
          </div>
          <div className="topbar-meta"><span>Secure session</span><strong>{dashboard?.stats?.items ?? 0} materials</strong></div>
          {message && <div className="toast">{message}</div>}
        </header>
        <View view={view} api={api} refresh={refresh} dashboard={dashboard} erp={erp} users={users} currentUser={user} setMessage={setMessage} search={search} setSearch={setSearch} />
      </main>
    </div>
  );
}

function AuthScreen({ auth, setAuth, authTab, setAuthTab, submit, message }) {
  const set = event => setAuth({ ...auth, [event.target.name]: event.target.value });
  return (
    <main className="hero">
      <section>
        <p className="eyebrow">React + Python + MongoDB</p>
        <h1>ERP Management System</h1>
        <p>Register your company, manage sales, procurement, GRN material, production, invoices, finance, HR, reports, and AI order suggestions.</p>
        <div className="hero-metrics">
          <div className="metric"><strong>GRN</strong><span>Inward material entry</span></div>
          <div className="metric"><strong>QC</strong><span>Production workflow</span></div>
          <div className="metric"><strong>DC</strong><span>Invoice documents</span></div>
        </div>
      </section>
      <section className="auth-panel">
        <div className="tabs">
          {["login", "owner", "staff"].map(tab => <button key={tab} className={authTab === tab ? "tab active" : "tab"} onClick={() => setAuthTab(tab)}>{tab}</button>)}
        </div>
        <form className="form" onSubmit={submit}>
          <h2>{authTab === "login" ? "Login" : authTab === "owner" ? "Owner register" : "Staff register"}</h2>
          {authTab !== "login" && <Input label="Company name" name="companyName" value={auth.companyName} onChange={set} />}
          {authTab === "owner" && <Input label="Company address" name="address" value={auth.address} onChange={set} />}
          {authTab !== "login" && <Input label="Name" name="name" value={auth.name} onChange={set} />}
          {authTab === "staff" && <label className="field"><span>Role</span><select name="role" value={auth.role} onChange={set}><option value="manager">Manager</option><option value="employee">Employee</option></select></label>}
          {authTab === "login" && <Input label="Company name" name="companyName" value={auth.companyName} onChange={set} />}
          {authTab === "login" ? <Input label="Phone or email" name="identity" value={auth.identity} onChange={set} /> : <Input label="Phone" name="phone" value={auth.phone} onChange={set} />}
          {authTab !== "login" && <Input label="Email" name="email" value={auth.email} onChange={set} />}
          <Input label="Password" name="password" type="password" value={auth.password} onChange={set} />
          {authTab !== "login" && <p className="form-note">Use at least 8 characters with letters and numbers.</p>}
          {message && <div className="message">{message}</div>}
          <button className="btn" type="submit">{authTab === "login" ? "Login" : "Register"}</button>
        </form>
      </section>
    </main>
  );
}

function View(props) {
  if (props.view === "profile") return <Profile user={props.currentUser} />;
  if (props.view === "erp") return <ErpMenu {...props} />;
  if (props.view === "ai-advisor") return <AiAdvisor {...props} />;
  if (props.view === "sales") return <Sales {...props} />;
  if (props.view === "invoices") return <InvoiceMenu {...props} />;
  if (props.view === "process") return <ProcessMenu {...props} />;
  if (props.view === "machining") return <MachiningMenu {...props} />;
  if (props.view === "cnc-machines") return <CncMachines {...props} />;
  if (props.view === "salary") return <Salary {...props} />;
  if (props.view === "workers") return <WorkersMenu {...props} />;
  return <Dashboard {...props} />;
}

function Dashboard({ dashboard, api, refresh, setMessage }) {
  const stats = dashboard?.stats || {};
  return (
    <>
      <section className="command-center">
        <div>
          <p className="eyebrow">Production overview</p>
          <h3>{dashboard?.company?.name || "Inventory"} control room</h3>
        </div>
        <div className="quick-stats">
          {["items", "totalUnits", "machining", "inspectionPending"].map(key => <Stat key={key} label={label(key)} value={stats[key]} />)}
        </div>
      </section>
      <div className="stage-board">
        <Stage label="Process pending" value={stats.processPending} tone="blue" />
        <Stage label="In machining" value={stats.machining} tone="amber" />
        <Stage label="OK items" value={stats.okItems} tone="green" />
        <Stage label="Not OK items" value={stats.notOkItems} tone="red" />
      </div>
      <Panel title="Goods Receipt Note entry">
        <DataForm fields={arrivalFields()} submitText="Save GRN and generate inward GRN" onSubmit={async body => {
          const data = await api.post("/api/inventory/arrival", body);
          setMessage(data.message);
          refresh();
        }} />
      </Panel>
    </>
  );
  }
  
const erpCategories = [
  { id: "dashboard", label: "ERP Dashboard", title: "Overview" },
  { id: "finance", label: "Finance", title: "Financials" },
  { id: "reports", label: "Reports", title: "Reports" }
];

function ErpMenu(props) {
  const [categoryId, setCategoryId] = useState("dashboard");
  const category = erpCategories.find(item => item.id === categoryId) || erpCategories[0];
  
  return (
    <Panel title="Enterprise Resource Planning">
      <div className="invoice-workspace">
        <div className="invoice-shell">
          <aside className="invoice-parts" style={{ minWidth: 260 }}>
            <div className="invoice-section-title">
              <strong>ERP Modules ({erpCategories.length})</strong>
              <span>Select module</span>
            </div>
            <div className="invoice-part-list">
              {erpCategories.map(item => (
                <button type="button" className={`invoice-part ${item.id === category.id ? "active" : ""}`} key={item.id} onClick={() => setCategoryId(item.id)}>
                  <span className={`part-step ${item.id === category.id ? "current" : ""}`}>{item.id === category.id ? ">" : ""}</span>
                  <div>
                    <strong>{item.label}</strong>
                    <span>Module</span>
                  </div>
                  <small>ERP feature</small>
                  <span className="part-chevron">&gt;</span>
                </button>
              ))}
            </div>
          </aside>
          <section className="invoice-detail" style={{ background: "transparent", padding: 0, boxShadow: "none", border: "none" }}>
            {category.id === "dashboard" && <ErpDashboard {...props} />}
            {category.id === "finance" && <Finance {...props} />}
            {category.id === "reports" && <Reports {...props} />}
          </section>
        </div>
      </div>
    </Panel>
  );
}

function ErpDashboard({ erp }) {
  const summary = erp?.summary || {};
  return (
    <>
      <section className="command-center">
        <div>
          <p className="eyebrow">ERP overview</p>
          <h3>Business control center</h3>
        </div>
        <div className="quick-stats">
          <Stat label="Revenue" value={currency(summary.revenue)} />
          <Stat label="Net estimate" value={currency(summary.estimatedNet)} />
          <Stat label="Open sales orders" value={summary.openSalesOrders ?? 0} />
          <Stat label="Pending production" value={summary.pendingProduction ?? 0} />
        </div>
      </section>
      <div className="stage-board">
        <Stage label="Procurement value" value={currency(summary.procurementValue)} tone="blue" />
        <Stage label="Salary cost" value={currency(summary.salaryCost)} tone="amber" />
        <Stage label="Operating expense" value={currency(summary.operatingExpense)} tone="red" />
        <Stage label="Invoices" value={erp?.invoices?.length ?? 0} tone="green" />
      </div>
      <Panel title="ERP work queues">
        <div className="erp-queues">
          <QueueCard title="Sales orders" value={erp?.salesOrders?.length || 0} detail="Customer orders tracked before production" />
          <QueueCard title="Purchase orders" value={erp?.purchaseOrders?.length || 0} detail="Supplier and rate planning" />
          <QueueCard title="Inventory items" value={erp?.inventory?.length || 0} detail="GRN and production material records" />
          <QueueCard title="Expenses" value={erp?.expenses?.length || 0} detail="Operating cost entries" />
        </div>
      </Panel>
    </>
  );
}

function Sales({ erp, api, refresh, setMessage }) {
  return (
    <Panel title="Sales orders">
      <DataForm fields={salesFields()} submitText="Save sales order" onSubmit={async body => { const data = await api.post("/api/erp/sales-orders", body); setMessage(data.message); refresh(); }} />
      <Table rows={erp?.salesOrders || []} columns={["orderNumber", "customerName", "drawingNo", "description", "quantity", "rate", "totalValue", "dueDate", "status"]} action={order => (
        <select value={order.status || "open"} onChange={async event => { const data = await api.patch(`/api/erp/sales-orders/${order.id}/status`, { status: event.target.value }); setMessage(data.message); refresh(); }}>
          <option value="open">Open</option>
          <option value="in_production">In production</option>
          <option value="completed">Completed</option>
          <option value="cancelled">Cancelled</option>
        </select>
      )} />
    </Panel>
  );
}

function Finance({ erp, api, refresh, setMessage }) {
  const summary = erp?.summary || {};
  return (
    <>
      <div className="advisor-grid">
        <Stat label="Revenue" value={currency(summary.revenue)} />
        <Stat label="Expenses" value={currency(summary.operatingExpense)} />
        <Stat label="Salary" value={currency(summary.salaryCost)} />
        <Stat label="Net estimate" value={currency(summary.estimatedNet)} />
      </div>
      <Panel title="Expense entry">
        <DataForm fields={expenseFields()} submitText="Save expense" onSubmit={async body => { const data = await api.post("/api/erp/expenses", body); setMessage(data.message); refresh(); }} />
        <Table rows={erp?.expenses || []} columns={["expenseDate", "category", "description", "amount", "paidBy", "createdAt"]} />
      </Panel>
    </>
  );
}

function Reports({ erp, dashboard }) {
  const stats = dashboard?.stats || {};
  const summary = erp?.summary || {};
  const rows = [
    { id: "r1", report: "Revenue", value: currency(summary.revenue), note: "Invoices plus sales order value" },
    { id: "r2", report: "Estimated net", value: currency(summary.estimatedNet), note: "Revenue minus salary and expenses" },
    { id: "r3", report: "Total units", value: stats.totalUnits ?? 0, note: "Total GRN quantity" },
    { id: "r4", report: "OK items", value: stats.okItems ?? 0, note: "Inspection OK quantity" },
    { id: "r5", report: "Not OK items", value: stats.notOkItems ?? 0, note: "Rejected quantity" },
    { id: "r6", report: "Open sales orders", value: summary.openSalesOrders ?? 0, note: "Pending customer orders" }
  ];
  return <Panel title="ERP reports"><Table rows={rows} columns={["report", "value", "note"]} /></Panel>;
}

function AiAdvisor({ api, setMessage }) {
  const [advisor, setAdvisor] = useState(null);
  const [loading, setLoading] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [chatLanguage, setChatLanguage] = useState("en");
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState([{ role: "assistant", text: helpText.en.greeting }]);

  async function runAdvisor() {
    setLoading(true);
    try {
      const data = await api.get("/api/ai/advisor");
      setAdvisor(data);
      setMessage("AI advisor model updated from current data.");
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { runAdvisor(); }, []);
  useEffect(() => () => stopAdvisorVoice(), []);

  function advisorSpeechText() {
    const top = advisor?.topProfitItems?.slice(0, 3) || [];
    const orders = advisor?.newOrderIdeas?.slice(0, 3) || [];
    const risks = advisor?.riskWarnings?.slice(0, 2) || [];
    const process = advisor?.processModel?.slice(0, 2) || [];
    const machining = advisor?.machiningModel?.slice(0, 2) || [];
    const lines = [
      `AI Advisor summary.`,
      `Estimated profit is ${currency(summary.estimatedProfit)}. Net after salary is ${currency(summary.netAfterSalary)}.`,
      summary.bestItem ? `The best item is ${summary.bestItem}.` : "",
      top.length ? `Most profitable items are ${top.map(item => `${item.description}, with AI score ${item.aiScore} percent`).join("; ")}.` : "",
      orders.length ? `Suggested new orders are ${orders.map(item => item.description).join("; ")}.` : "",
      risks.length ? `Quality risk warnings are ${risks.map(item => `${item.description}, quality score ${item.qualityScore} percent`).join("; ")}.` : "No major quality risk warnings found.",
      process.length ? `Process model priorities are ${process.map(item => `${item.description}, ${item.pendingQuantity} pending`).join("; ")}.` : "",
      machining.length ? `Machining model priorities are ${machining.map(item => `${item.description}, ${item.inMachiningQuantity} in machining`).join("; ")}.` : "",
    ];
    return lines.filter(Boolean).join(" ");
  }

  function speakAdvisor() {
    if (!advisor) {
      setMessage("Run the AI model before using voice suggestions.");
      return;
    }
    if (!("speechSynthesis" in window)) {
      setMessage("Voice suggestions are not supported in this browser.");
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(advisorSpeechText());
    utterance.rate = 0.95;
    utterance.pitch = 1;
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    setSpeaking(true);
    window.speechSynthesis.speak(utterance);
  }

  function stopAdvisorVoice() {
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    setSpeaking(false);
  }

  function askHelp(event) {
    event.preventDefault();
    const question = chatInput.trim();
    if (!question) return;
    const answer = appHelpAnswer(question, chatLanguage);
    setChatMessages([...chatMessages, { role: "user", text: question }, { role: "assistant", text: answer }]);
    setChatInput("");
  }

  function changeChatLanguage(language) {
    setChatLanguage(language);
    setChatMessages([{ role: "assistant", text: helpText[language].greeting }]);
  }

  const summary = advisor?.summary || {};
  return (
    <Panel title="AI order advisor">
      <div className="advisor-hero">
        <div>
          <p className="eyebrow">{advisor?.model?.name || "Inventory Order Advisor v1"}</p>
          <h3>Profit suggestions and new order predictions</h3>
          <p>The advisor now runs separate order, process, and machining scoring models from the current shop data.</p>
        </div>
        <div className="advisor-actions">
          <button className="btn" onClick={runAdvisor}>{loading ? "Analyzing..." : "Run AI model"}</button>
          <button className="btn secondary" onClick={speakAdvisor}>{speaking ? "Speaking..." : "Speak suggestions"}</button>
          {speaking && <button className="btn danger" onClick={stopAdvisorVoice}>Stop voice</button>}
        </div>
      </div>
      <div className="advisor-grid">
        <Stat label="Estimated revenue" value={currency(summary.estimatedRevenue)} />
        <Stat label="Estimated profit" value={currency(summary.estimatedProfit)} />
        <Stat label="Net after salary" value={currency(summary.netAfterSalary)} />
        <Stat label="Best item" value={summary.bestItem || "-"} />
        <Stat label="Process backlog" value={summary.processBacklog ?? 0} />
        <Stat label="Machining backlog" value={summary.machiningBacklog ?? 0} />
      </div>
      <div className="model-strip">
        {["order", "process", "machining"].map(key => {
          const model = advisor?.models?.[key];
          if (!model) return null;
          return <div className="model-chip" key={key}><strong>{model.name}</strong><span>{model.itemsScored} drawing(s)</span></div>;
        })}
      </div>
      <AdvisorSection title="Most profitable items" rows={advisor?.topProfitItems || []} />
      <AdvisorSection title="New orders to target" rows={advisor?.newOrderIdeas || []} />
      <AdvisorSection title="Quality risk warnings" rows={advisor?.riskWarnings || []} emptyText="No major quality risks found." />
      <AdvisorSection title="Process model priorities" rows={advisor?.processModel || []} emptyText="No process model data yet." />
      <AdvisorSection title="Machining model priorities" rows={advisor?.machiningModel || []} emptyText="No machining model data yet." />
      <div className="guidance-list">
        {(advisor?.guidance || []).map(text => <div key={text}>{text}</div>)}
      </div>
      <section className="ai-chat">
        <div className="panel-head">
          <h3>App help chat</h3>
          <select value={chatLanguage} onChange={event => changeChatLanguage(event.target.value)}>
            {helpLanguages.map(([value, labelText]) => <option key={value} value={value}>{labelText}</option>)}
          </select>
        </div>
        <div className="chat-window">
          {chatMessages.map((message, index) => <div key={`${message.role}-${index}`} className={`chat-bubble ${message.role}`}>{message.text}</div>)}
        </div>
        <form className="chat-form" onSubmit={askHelp}>
          <input value={chatInput} onChange={event => setChatInput(event.target.value)} placeholder="Ask how to use this app" />
          <button className="btn" type="submit">Ask</button>
        </form>
      </section>
    </Panel>
  );
}

function AdvisorSection({ title, rows, emptyText = "No suggestions yet. Add more GRN, purchase order, and invoice data." }) {
  return (
    <section className="advisor-section">
      <div className="panel-head"><h3>{title}</h3></div>
      {!rows.length ? <div className="empty">{emptyText}</div> : (
        <div className="advisor-list">
          {rows.map(row => (
            <article className="advisor-card" key={`${title}-${row.drawingNo}-${row.description}`}>
              <div>
                <strong>{row.description}</strong>
                <span>{row.drawingNo}</span>
              </div>
              <div className="advisor-score"><b>{row.aiScore}%</b><span>AI score</span></div>
              <div className="advisor-metrics">
                {(row.metrics || [
                  `Profit ${currency(row.estimatedProfit)}`,
                  `Per item ${currency(row.profitPerItem)}`,
                  `Quality ${row.qualityScore}%`,
                  `Demand ${row.demandScore}%`
                ]).map(metric => <span key={metric}>{metric}</span>)}
              </div>
              <p>{row.action}. {row.reason}</p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

const invoiceCategories = [
  { id: "search", title: "Invoice Search", label: "Search", docTypes: ["inward_grn_invoice", "incoming_dc_invoice", "cnc_machining_document", "hs_ok_bill", "working_material_invoice", "outgoing_ok_invoice", "not_ok_loss_dc", "process_rejected_loss_dc", "ok_inspection_report"], empty: "Enter a heat no to display matching invoice files." },
  { id: "incoming", title: "Incoming GRN Invoice", label: "Incoming GRN", docTypes: ["inward_grn_invoice", "incoming_dc_invoice"], empty: "No incoming GRN invoices yet." },
  { id: "outgoing", title: "Outgoing Invoice", label: "Outgoing", docTypes: ["hs_ok_bill", "working_material_invoice", "outgoing_ok_invoice", "not_ok_loss_dc", "process_rejected_loss_dc"], empty: "No outgoing invoices generated yet." },
  { id: "ok", title: "OK Invoice", label: "OK Invoice", docTypes: ["working_material_invoice", "hs_ok_bill", "outgoing_ok_invoice", "ok_inspection_report"], empty: "No OK invoices yet." },
  { id: "not-ok", title: "Not OK Invoice", label: "Not OK", docTypes: ["not_ok_loss_dc", "process_rejected_loss_dc"], empty: "No not OK invoices yet." }
];

function InvoiceMenu({ dashboard, search, setSearch }) {
  const [categoryId, setCategoryId] = useState("search");
  const [selection, setSelection] = useState(null);
  const category = invoiceCategories.find(item => item.id === categoryId) || invoiceCategories[0];
  const allItems = dashboard?.inventory || [];
  const query = search.trim();
  const rows = invoiceRows(allItems, category.docTypes, category.id === "search" ? search : search);
  const visibleRows = category.id === "search" && !query ? [] : rows;
  const selectedItem = visibleRows.find(item => item.id === selection?.itemId) || visibleRows[0];
  const docs = selectedItem ? itemDocuments(selectedItem, category.docTypes) : [];
  const allDocCount = invoiceCategories.slice(1).reduce((sum, item) => sum + invoiceRows(allItems, item.docTypes, "").reduce((docSum, row) => docSum + itemDocuments(row, item.docTypes).length, 0), 0);
  const activeDocCount = visibleRows.reduce((sum, item) => sum + itemDocuments(item, category.docTypes).length, 0);
  const percent = allDocCount ? Math.round((activeDocCount / allDocCount) * 100) : 0;

  return (
    <Panel title="Invoices">
      <Search value={search} setValue={setSearch} count={visibleRows.length} placeholder="Enter heat no or leave empty for category invoices" />
      <div className="invoice-workspace">
        <div className="invoice-progress">
          <strong>Invoice Menu</strong>
          <span>{activeDocCount} of {allDocCount} Files In This View</span>
          <div className="progress-track"><span style={{ width: `${percent}%` }} /></div>
          <b>{percent}%</b>
        </div>
        <div className="invoice-shell">
          <aside className="invoice-parts">
            <div className="invoice-section-title">
              <strong>Invoice Categories ({invoiceCategories.length})</strong>
              <span>{visibleRows.length} record(s)</span>
            </div>
            <div className="invoice-part-list">
              {invoiceCategories.map(item => {
                const categoryRows = item.id === "search" && !query ? [] : invoiceRows(allItems, item.docTypes, item.id === "search" ? search : search);
                const count = categoryRows.reduce((sum, row) => sum + itemDocuments(row, item.docTypes).length, 0);
                return (
                  <button type="button" className={`invoice-part ${item.id === category.id ? "active" : ""}`} key={item.id} onClick={() => { setCategoryId(item.id); setSelection(null); }}>
                    <span className={`part-step ${item.id === category.id ? "current" : count ? "done" : ""}`}>{item.id === category.id ? ">" : count ? "OK" : ""}</span>
                    <div>
                      <strong>{item.label}</strong>
                      <span>{count} file(s)</span>
                    </div>
                    <small>{item.id === "search" ? "Heat no search" : "Invoice list"}</small>
                    <span className="part-chevron">&gt;</span>
                  </button>
                );
              })}
            </div>
          </aside>
          <section className="invoice-detail">
            <div className="invoice-section-title">
              <strong>{category.title}</strong>
              <span>{selectedItem?.drawingNo || selectedItem?.productDescription || "No invoice selected"}</span>
            </div>
            {!visibleRows.length ? (
              <div className="empty">{category.empty}</div>
            ) : (
              <>
                <div className="current-part-card">
                  <div className="part-emblem">IV</div>
                  <div>
                    <span>You are viewing</span>
                    <h3>{selectedItem?.dcInvoiceNumber || selectedItem?.materialCode || selectedItem?.drawingNo || "Invoice"}</h3>
                    <p>Status: <b>{selectedItem?.stage || selectedItem?.inspectionStatus || selectedItem?.processStatus || "Generated"}</b></p>
                    <small>{selectedItem?.productDescription || selectedItem?.description || "-"} | Qty {selectedItem?.totalItems || selectedItem?.quantity || 0}</small>
                  </div>
                </div>
                <div className="invoice-doc-box">
                  <strong>Documents ({docs.length})</strong>
                  <Documents docs={docs} />
                </div>
                <div className="invoice-job-strip">
                  {visibleRows.map(item => (
                    <button type="button" key={item.id} className={item.id === selectedItem?.id ? "active" : ""} onClick={() => setSelection({ itemId: item.id })}>
                      <strong>{item.dcInvoiceNumber || item.materialCode || item.drawingNo}</strong>
                      <span>{item.productDescription || item.description}</span>
                    </button>
                  ))}
                </div>
              </>
            )}
          </section>
        </div>
      </div>
    </Panel>
  );
}

const workflowInfo = {
  process: {
    title: "Process",
    empty: "No process pending materials found.",
    docTypes: ["inward_grn_invoice", "incoming_dc_invoice"]
  },
  machining: {
    title: "Machining",
    empty: "No machining materials found.",
    docTypes: ["inward_grn_invoice", "incoming_dc_invoice", "cnc_machining_document", "working_material_invoice"]
  }
};

function ProcessMenu({ dashboard, api, refresh, setMessage, search, setSearch }) {
  const rows = filter(dashboard?.processMaterials || [], search);
  const [selection, setSelection] = useState(null);
  async function patch(path, body) {
    try {
      const data = await api.patch(path, body);
      setMessage(data.message);
      refresh();
    } catch (error) {
      setMessage(error.message);
    }
  }
  return (
    <Panel title="Process">
      <Search value={search} setValue={setSearch} count={rows.length} />
      <ProcessTable rows={rows} docTypes={workflowInfo.process.docTypes} selection={selection} setSelection={setSelection} onDecision={(item, part, decision) => patch(`/api/inventory/${workflowItemId(item)}/process`, { decision, partNo: part.partNo })} />
    </Panel>
  );
}

function MachiningMenu({ dashboard, api, refresh, setMessage, search, setSearch }) {
  const rows = filter(dashboard?.machiningJobs || [], search);
  const [selection, setSelection] = useState(null);
  async function patch(path, body) {
    try {
      const data = await api.patch(path, body);
      setMessage(data.message);
      refresh();
    } catch (error) {
      setMessage(error.message);
    }
  }
  return (
    <Panel title="Machining">
      <Search value={search} setValue={setSearch} count={rows.length} />
      <MachiningTable rows={rows} docTypes={workflowInfo.machining.docTypes} machines={dashboard?.mtconnectMachines || []} api={api} refresh={refresh} setMessage={setMessage} selection={selection} setSelection={setSelection} onComplete={(item, part) => patch(`/api/inventory/${workflowItemId(item)}/machining`, { partNo: part.partNo })} />
    </Panel>
  );
}

function ProcessTable({ rows, docTypes, selection, setSelection, onDecision }) {
  if (!rows.length) return <div className="empty">{workflowInfo.process.empty}</div>;
  const selectedItem = rows.find(item => item.id === selection?.itemId) || rows[0];
  const parts = Array.isArray(selectedItem.parts) ? selectedItem.parts : [];
  const selectedPart = parts.find(part => part.partNo === selection?.partNo) || parts.find(part => !["ok", "rejected"].includes(part.processStatus)) || parts[0];
  const checkedCount = parts.filter(part => part.processStatus === "ok" || part.processStatus === "rejected").length;
  const totalCount = parts.length || Number(selectedItem.quantity || 0);
  const okCount = parts.filter(part => part.processStatus === "ok").length;
  const rejectedCount = parts.filter(part => part.processStatus === "rejected").length;
  const percent = totalCount ? Math.round((checkedCount / totalCount) * 100) : 0;
  return (
    <div className="process-workspace">
      <div className="process-progress">
        <strong>Overall Progress</strong>
        <span>{checkedCount} of {totalCount} Parts Checked</span>
        <div className="progress-track"><span style={{ width: `${percent}%` }} /></div>
        <b>{percent}%</b>
      </div>
      <div className="process-shell">
        <aside className="process-parts">
          <div className="process-section-title">
            <strong>Parts Progress ({totalCount})</strong>
            <span>{okCount} OK / {rejectedCount} Rejected</span>
          </div>
          <ProcessPartActions item={selectedItem} selectedPart={selectedPart} setSelection={setSelection} />
        </aside>
        <section className="process-detail">
          <div className="process-section-title">
            <strong>Current Part Details</strong>
            <span>{selectedItem.description}</span>
          </div>
          {selectedPart && (
            <>
              <div className="current-part-card">
                <div className="part-emblem">PR</div>
                <div>
                  <span>You are checking</span>
                  <h3>Part {selectedPart.partNo}</h3>
                  <p>Status: <b>{processStatusLabel(selectedPart.processStatus)}</b></p>
                  <small>{selectedPart.heatNo || "No heat no"} | Drawing {selectedItem.drawingNo || "-"}</small>
                </div>
              </div>
              <div className="process-note-box">
                <strong>Instructions / Notes</strong>
                <p>Review the incoming part details, then mark this part as OK or Reject. OK parts move to Machining after all processing decisions are complete.</p>
                {selectedPart.processCheckedAt && <p>Checked at {formatDateTime(selectedPart.processCheckedAt)}</p>}
              </div>
              <div className="process-doc-box">
                <strong>Documents ({itemDocuments(selectedItem, docTypes).length})</strong>
                <Documents docs={itemDocuments(selectedItem, docTypes)} />
              </div>
              <div className="process-actions">
                <button className="btn" type="button" disabled={selectedPart.processStatus === "ok"} onClick={() => onDecision(selectedItem, selectedPart, "ok")}>Mark Part {selectedPart.partNo} as OK</button>
                <button className="btn danger" type="button" disabled={selectedPart.processStatus === "rejected"} onClick={() => onDecision(selectedItem, selectedPart, "rejected")}>Reject Part {selectedPart.partNo}</button>
              </div>
            </>
          )}
        </section>
      </div>
      {rows.length > 1 && (
        <div className="process-job-strip">
          {rows.map(item => (
            <button type="button" key={item.id} className={item.id === selectedItem.id ? "active" : ""} onClick={() => setSelection({ itemId: item.id, partNo: item.parts?.[0]?.partNo })}>
              <strong>{item.processCode || item.drawingNo}</strong>
              <span>{item.description}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function ProcessPartActions({ item, selectedPart, setSelection }) {
  const parts = Array.isArray(item.parts) ? item.parts : [];
  return (
    <div className="process-part-list">
      {parts.map(part => {
        const decided = part.processStatus === "ok" || part.processStatus === "rejected";
        return (
          <button type="button" className={`process-part ${selectedPart?.partNo === part.partNo ? "active" : ""}`} key={`${item.id}-${part.partNo}`} onClick={() => setSelection({ itemId: item.id, partNo: part.partNo })}>
            <span className={`part-step ${part.processStatus === "ok" ? "done" : part.processStatus === "rejected" ? "rejected" : selectedPart?.partNo === part.partNo ? "current" : ""}`}>{part.processStatus === "ok" ? "OK" : part.processStatus === "rejected" ? "NO" : selectedPart?.partNo === part.partNo ? ">" : ""}</span>
            <div>
              <strong>Part {part.partNo}</strong>
              <span>{processStatusLabel(part.processStatus)}</span>
            </div>
            <small>{decided && part.processCheckedAt ? formatDateTime(part.processCheckedAt) : part.heatNo || "-"}</small>
            <span className="part-chevron">&gt;</span>
          </button>
        );
      })}
    </div>
  );
}

function MachiningTable({ rows, docTypes, machines, api, refresh, setMessage, selection, setSelection, onComplete }) {
  if (!rows.length) return <div className="empty">{workflowInfo.machining.empty}</div>;
  const selectedItem = rows.find(item => item.id === selection?.itemId) || rows[0];
  const parts = Array.isArray(selectedItem.parts) ? selectedItem.parts : [];
  const selectedPart = parts.find(part => part.partNo === selection?.partNo) || parts.find(part => part.machiningStatus !== "completed") || parts[0];
  const completedCount = parts.filter(part => part.machiningStatus === "completed").length;
  const totalCount = parts.length || Number(selectedItem.quantity || 0);
  const percent = totalCount ? Math.round((completedCount / totalCount) * 100) : 0;
  return (
    <div className="machining-workspace">
      <div className="machining-progress">
        <strong>Overall Progress</strong>
        <span>{completedCount} of {totalCount} Parts Completed</span>
        <div className="progress-track"><span style={{ width: `${percent}%` }} /></div>
        <b>{percent}%</b>
      </div>
      <div className="machining-shell">
        <aside className="machining-parts">
          <div className="machining-section-title">
            <strong>Parts Progress ({totalCount})</strong>
            <span>{selectedItem.jobNo || selectedItem.drawingNo}</span>
          </div>
          <MachiningPartActions item={selectedItem} selectedPart={selectedPart} setSelection={setSelection} />
        </aside>
        <section className="machining-detail">
          <div className="machining-section-title">
            <strong>Current Part Details</strong>
            <span>{selectedItem.description}</span>
          </div>
          {selectedPart && (
            <>
              <div className="current-part-card">
                <div className="part-emblem">MC</div>
                <div>
                  <span>You are working on</span>
                  <h3>Part {selectedPart.partNo}</h3>
                  <p>Status: <b>{selectedPart.machiningStatus === "completed" ? "Completed" : "Pending"}</b></p>
                  <small>{selectedPart.heatNo || "No heat no"} | Drawing {selectedItem.drawingNo || "-"}</small>
                </div>
              </div>
              <div className="machining-note-box">
                <strong>Instructions / Notes</strong>
                <p>Review the current part, confirm the CNC machining details, then mark this part as complete when the work is done.</p>
                {selectedPart.machiningCompletedAt && <p>Completed at {formatDateTime(selectedPart.machiningCompletedAt)}</p>}
              </div>
              <div className="machining-doc-box">
                <strong>Documents ({itemDocuments(selectedItem, docTypes).length})</strong>
                <Documents docs={itemDocuments(selectedItem, docTypes)} />
              </div>
              <div className="machining-actions">
                <button className="btn" type="button" disabled={selectedPart.machiningStatus === "completed"} onClick={() => onComplete(selectedItem, selectedPart)}>Mark Part {selectedPart.partNo} as Complete</button>
                <CncMachiningForm item={selectedItem} machines={machines} api={api} refresh={refresh} setMessage={setMessage} />
                {selectedItem.machiningStatus === "completed" && <InspectionForm item={selectedItem} api={api} refresh={refresh} setMessage={setMessage} />}
              </div>
            </>
          )}
        </section>
      </div>
      {rows.length > 1 && (
        <div className="machining-job-strip">
          {rows.map(item => (
            <button type="button" key={item.id} className={item.id === selectedItem.id ? "active" : ""} onClick={() => setSelection({ itemId: item.id, partNo: item.parts?.[0]?.partNo })}>
              <strong>{item.jobNo || item.drawingNo}</strong>
              <span>{item.description}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function MachiningPartActions({ item, selectedPart, setSelection }) {
  const parts = Array.isArray(item.parts) ? item.parts : [];
  return (
    <div className="machining-part-list">
      {parts.map(part => {
        const completed = part.machiningStatus === "completed";
        return (
          <button type="button" className={`machining-part ${selectedPart?.partNo === part.partNo ? "active" : ""}`} key={`${item.id}-${part.partNo}`} onClick={() => setSelection({ itemId: item.id, partNo: part.partNo })}>
            <span className={`part-step ${completed ? "done" : selectedPart?.partNo === part.partNo ? "current" : ""}`}>{completed ? "OK" : selectedPart?.partNo === part.partNo ? ">" : ""}</span>
            <div>
              <strong>Part {part.partNo}</strong>
              <span>{completed ? "Completed" : "Pending"}</span>
            </div>
            <small>{completed && part.machiningCompletedAt ? formatDateTime(part.machiningCompletedAt) : part.heatNo || "-"}</small>
            <span className="part-chevron">&gt;</span>
          </button>
        );
      })}
    </div>
  );
}

function CncMachines({ api, refresh, setMessage, dashboard }) {
  const [statuses, setStatuses] = useState([]);
  const [loading, setLoading] = useState(false);

  async function loadStatuses() {
    setLoading(true);
    try {
      const data = await api.get("/api/mtconnect/machines/status");
      setStatuses(data.machines || []);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadStatuses(); }, []);

  return (
    <Panel title="CNC machines">
      <DataForm fields={[["name", "Machine name"], ["agentUrl", "MTConnect Agent URL"], ["deviceName", "Device name"]]} submitText="Connect CNC machine" onSubmit={async body => { const data = await api.post("/api/mtconnect/machines", body); setMessage(data.message); await refresh(); await loadStatuses(); }} />
      <div className="panel-head">
        <h3>Live MTConnect status</h3>
        <button className="btn secondary compact" onClick={loadStatuses}>{loading ? "Checking..." : "Refresh"}</button>
      </div>
      <MachineCards machines={statuses.length ? statuses : (dashboard?.mtconnectMachines || [])} api={api} refresh={refresh} setMessage={setMessage} reload={loadStatuses} />
    </Panel>
  );
}

function MachineCards({ machines, api, refresh, setMessage, reload }) {
  if (!machines.length) return <div className="empty">No CNC machines connected yet. Add the MTConnect Agent URL from your machine gateway.</div>;
  return (
    <div className="machine-grid">
      {machines.map(machine => {
        const current = machine.current || {};
        return (
          <article className="machine-card" key={machine.id}>
            <div className="machine-head">
              <div>
                <strong>{machine.name}</strong>
                <span>{machine.agentUrl}</span>
              </div>
              <span className={`status-dot ${machine.connected ? "online" : "offline"}`}>{machine.connected ? machine.state : "offline"}</span>
            </div>
            <div className="machine-metrics">
              <div><span>Execution</span><b>{current.execution || "-"}</b></div>
              <div><span>Program</span><b>{current.program || "-"}</b></div>
              <div><span>Parts</span><b>{current.partCount || "-"}</b></div>
              <div><span>Feedrate</span><b>{current.pathFeedrate || "-"}</b></div>
              <div><span>Spindle</span><b>{current.spindleSpeed || "-"}</b></div>
              <div><span>E-stop</span><b>{current.emergencyStop || "-"}</b></div>
            </div>
            {current.conditions?.length > 0 && <div className="condition-list">{current.conditions.map(condition => <span key={`${condition.level}-${condition.name}`}>{condition.level}: {condition.name}</span>)}</div>}
            {machine.message && <p className="machine-message">{machine.message}</p>}
            <div className="row-actions">
              <button className="btn secondary compact" onClick={reload}>Check</button>
              <button className="btn danger compact" onClick={async () => { const data = await api.request(`/api/mtconnect/machines/${machine.id}`, { method: "DELETE" }); setMessage(data.message); await refresh(); await reload(); }}>Remove</button>
            </div>
          </article>
        );
      })}
    </div>
  );
}

function CncMachiningForm({ item, machines, api, refresh, setMessage }) {
  const [form, setForm] = useState({ heatNo: item.lastCncHeatNo || item.heatNo || "", machineId: item.mtconnectMachineId || "", program: "", partCount: "", remarks: "" });
  const itemId = workflowItemId(item);
  async function updateMachine(machineId) {
    try {
      setForm({ ...form, machineId });
      const data = await api.patch(`/api/inventory/${itemId}/machine`, { machineId });
      setMessage(data.message);
      refresh();
    } catch (error) {
      setMessage(error.message);
    }
  }
  async function saveDocument() {
    try {
      const data = await api.post(`/api/inventory/${itemId}/cnc-machining`, form);
      setMessage(data.message);
      refresh();
    } catch (error) {
      setMessage(error.message);
    }
  }
  return (
    <div className="cnc-run-form">
      <label><span>Heat no</span><input value={form.heatNo} onChange={event => setForm({ ...form, heatNo: event.target.value })} placeholder="Raw material heat no" /></label>
      <label><span>CNC</span><select value={form.machineId} onChange={event => updateMachine(event.target.value)}><option value="">Choose machine</option>{machines.map(machine => <option key={machine.id} value={machine.id}>{machine.name}</option>)}</select></label>
      <label><span>Program</span><input value={form.program} onChange={event => setForm({ ...form, program: event.target.value })} placeholder="Optional" /></label>
      <label><span>Part count</span><input type="number" value={form.partCount} onChange={event => setForm({ ...form, partCount: event.target.value })} placeholder="Optional" /></label>
      <label className="wide"><span>Remarks</span><input value={form.remarks} onChange={event => setForm({ ...form, remarks: event.target.value })} placeholder="Optional machining note" /></label>
      <button className="btn secondary" type="button" onClick={saveDocument}>Save CNC document</button>
    </div>
  );
  }
  
const workersCategories = [
  { id: "managers", label: "Managers", title: "Managers" },
  { id: "employees", label: "Employees", title: "Employees" },
  { id: "requests", label: "Requests", title: "Approval requests" }
];

function WorkersMenu(props) {
  const [categoryId, setCategoryId] = useState("managers");
  const category = workersCategories.find(item => item.id === categoryId) || workersCategories[0];
  
  return (
    <Panel title="Workers & Users">
      <div className="invoice-workspace">
        <div className="invoice-shell">
          <aside className="invoice-parts" style={{ minWidth: 260 }}>
            <div className="invoice-section-title">
              <strong>Worker Roles ({workersCategories.length})</strong>
              <span>Select category</span>
            </div>
            <div className="invoice-part-list">
              {workersCategories.map(item => (
                <button type="button" className={`invoice-part ${item.id === category.id ? "active" : ""}`} key={item.id} onClick={() => setCategoryId(item.id)}>
                  <span className={`part-step ${item.id === category.id ? "current" : ""}`}>{item.id === category.id ? ">" : ""}</span>
                  <div>
                    <strong>{item.label}</strong>
                    <span>Category</span>
                  </div>
                  <small>Workers section</small>
                  <span className="part-chevron">&gt;</span>
                </button>
              ))}
            </div>
          </aside>
          <section className="invoice-detail" style={{ background: "transparent", padding: 0, boxShadow: "none", border: "none" }}>
            {category.id === "managers" && <People role="manager" {...props} />}
            {category.id === "employees" && <People role="employee" {...props} />}
            {category.id === "requests" && <Requests {...props} />}
          </section>
        </div>
      </div>
    </Panel>
  );
}

function Salary({ users, dashboard, api, refresh, setMessage }) {
  const employees = users.filter(user => user.role === "employee" && user.status === "approved");
  return <Panel title="Salary calculator"><DataForm fields={[["employeeId", "Employee", "select", employees.map(e => [e.id, e.name])], ["ratePerHour", "Rate per hour", "number"], ["inTime", "In time", "datetime-local"], ["outTime", "Out time", "datetime-local"]]} submitText="Calculate salary" onSubmit={async body => { const data = await api.post("/api/salary", body); setMessage(data.message); refresh(); }} /><Table rows={dashboard?.salaryRecords || []} columns={["employeeName", "ratePerHour", "hours", "totalSalary", "createdAt"]} /></Panel>;
}

function People({ role, users }) {
  return <Panel title={role === "manager" ? "Managers" : "Employees"}><UserTable rows={users.filter(user => user.role === role && user.status === "approved")} /></Panel>;
}

function Requests({ users, api, refresh, setMessage }) {
  const pending = users.filter(user => user.status === "pending");
  return <Panel title="Approval requests"><UserTable rows={pending} action={user => <><button className="btn" onClick={async () => { await api.patch(`/api/users/${user.id}/status`, { status: "approved" }); setMessage("User approved."); refresh(); }}>Approve</button><button className="btn danger" onClick={async () => { await api.patch(`/api/users/${user.id}/status`, { status: "rejected" }); setMessage("User rejected."); refresh(); }}>Reject</button></>} /></Panel>;
}

function Profile({ user }) {
  return <Panel title="Profile"><div className="profile-details">{Object.entries(user).filter(([, v]) => typeof v !== "object").map(([k, v]) => <div className="detail" key={k}><span>{label(k)}</span><strong>{String(v ?? "")}</strong></div>)}</div></Panel>;
}

function DataForm({ fields, submitText, onSubmit }) {
  const initial = Object.fromEntries(fields.map(([name, , type]) => [name, type === "date" ? new Date().toISOString().slice(0, 10) : type === "time" ? new Date().toTimeString().slice(0, 5) : ""]));
  const [form, setForm] = useState(initial);
  return <form className="form" onSubmit={async event => { event.preventDefault(); await onSubmit(form); setForm(initial); }}><div className="profile-details">{fields.map(([name, text, type = "text", options]) => type === "select" ? <label className="field" key={name}><span>{text}</span><select value={form[name]} onChange={e => setForm({ ...form, [name]: e.target.value })}><option value="">Choose</option>{options.map(([value, labelText]) => <option key={value} value={value}>{labelText}</option>)}</select></label> : type === "textarea" ? <Textarea key={name} label={text} name={name} value={form[name]} hint={options} onChange={e => setForm({ ...form, [name]: e.target.value })} /> : <Input key={name} label={text} name={name} type={type} value={form[name]} onChange={e => setForm({ ...form, [name]: e.target.value })} />)}</div><button className="btn" type="submit">{submitText}</button></form>;
}

function InspectionForm({ item, api, refresh, setMessage }) {
  const [okItems, setOkItems] = useState(item.quantity || item.totalItems || 0);
  const [notOkItems, setNotOkItems] = useState(0);
  const itemId = workflowItemId(item);
  async function saveInspection() {
    try {
      const data = await api.patch(`/api/inventory/${itemId}/inspection`, { okItems, notOkItems });
      setMessage(data.message);
      refresh();
    } catch (error) {
      setMessage(error.message);
    }
  }
  return <div className="inline-form"><input type="number" value={okItems} onChange={e => setOkItems(e.target.value)} /><input type="number" value={notOkItems} onChange={e => setNotOkItems(e.target.value)} /><button className="btn" type="button" onClick={saveInspection}>Save inspection</button></div>;
}

function InventoryTable({ rows, renderActions, docTypes, emptyText = "No records found." }) {
  if (!rows.length) return <div className="empty">{emptyText}</div>;
  const heads = renderActions ? ["Heat no by part", "Drawing", "Description", "Qty", "Stage", "Documents", "Action"] : ["Heat no by part", "Drawing", "Description", "Qty", "Stage", "Documents"];
  return <div className="table-wrap"><table><thead><tr>{heads.map(h => <th key={h}>{h}</th>)}</tr></thead><tbody>{rows.map(item => <tr key={item.id}><td><HeatNumbers item={item} /></td><td>{item.drawingNo}</td><td>{item.productDescription}</td><td>{item.totalItems}</td><td><span className="pill">{item.stage || item.processStatus}</span></td><td><Documents docs={docTypes ? itemDocuments(item, docTypes) : item.generatedDocuments} /></td>{renderActions && <td>{renderActions(item)}</td>}</tr>)}</tbody></table></div>;
}

function itemDocuments(item, docTypes) {
  return (item.generatedDocuments || []).filter(doc => docTypes.includes(doc.type));
}

function invoiceRows(items, docTypes, search = "") {
  return filter(items.filter(item => itemDocuments(item, docTypes).length > 0), search);
}

function HeatNumbers({ item }) {
  const parts = Array.isArray(item.parts) && item.parts.length
    ? item.parts
    : heatValues(item).map((heatNo, index) => ({ partNo: index + 1, heatNo }));
  if (!parts.length) return <strong>{item.heatNo || "-"}</strong>;
  return <div className="heat-list">{parts.map(part => <span key={`${part.partNo}-${part.heatNo}`}><b>Part {part.partNo}</b>{part.heatNo}</span>)}</div>;
}

function Documents({ docs = [] }) {
  const list = docs.filter(doc => doc.url);
  if (!list.length) return <span className="muted-text">No files yet</span>;
  
  const downloadFile = async (e, doc) => {
    e.preventDefault();
    try {
      const response = await fetch(`${API_BASE}${doc.url}`);
      const blob = await response.blob();
      const objectUrl = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      const ext = doc.url.split('.').pop() || "html";
      link.download = (doc.title || doc.name || doc.type || "Document") + "." + ext;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(objectUrl);
    } catch (err) {
      console.error("Download failed", err);
      window.open(`${API_BASE}${doc.url}`, "_blank");
    }
  };

  return (
    <div className="doc-files">
      {list.map(doc => (
        <div className="doc-file" key={`${doc.type}-${doc.url}`} title={doc.name || doc.title}>
          <span className="doc-icon" aria-hidden="true">{(doc.url.split('.').pop() || "DOC").toUpperCase()}</span>
          <span className="doc-meta">
            <strong>{doc.title || doc.name || "Document"}</strong>
            <small>{docLabel(doc.type)} file</small>
          </span>
          <a href={`${API_BASE}${doc.url}`} target="_blank" rel="noreferrer" className="doc-open" style={{ textDecoration: "none" }}>View</a>
          <button type="button" className="doc-open" style={{ border: "none", cursor: "pointer", background: "var(--brand)", color: "#fff" }} onClick={(e) => downloadFile(e, doc)}>Save</button>
        </div>
      ))}
    </div>
  );
}

function docLabel(type) {
  const labels = {
    inward_grn_invoice: "Incoming GRN",
    incoming_dc_invoice: "Incoming GRN",
    cnc_machining_document: "CNC machining",
    hs_ok_bill: "OK outgoing invoice",
    working_material_invoice: "Machining invoice",
    outgoing_ok_invoice: "OK outgoing invoice",
    not_ok_loss_dc: "Not OK invoice",
    process_rejected_loss_dc: "Rejected invoice",
    ok_inspection_report: "OK report"
  };
  return labels[type] || "Document";
}

function UserTable({ rows, action }) {
  if (!rows.length) return <div className="empty">No users found.</div>;
  return <Table rows={rows} columns={["name", "role", "phone", "email", "status", "ratePerHour"]} action={action} />;
}

function Table({ rows, columns, action }) {
  if (!rows.length) return <div className="empty">No records found.</div>;
  return <div className="table-wrap"><table><thead><tr>{columns.map(col => <th key={col}>{label(col)}</th>)}{action && <th>Action</th>}</tr></thead><tbody>{rows.map(row => <tr key={row.id}>{columns.map(col => <td key={col}>{String(row[col] ?? "")}</td>)}{action && <td className="row-actions">{action(row)}</td>}</tr>)}</tbody></table></div>;
}

function Panel({ title, children }) {
  return <section className="content-panel"><div className="panel-head"><h3>{title}</h3></div>{children}</section>;
}

function Input({ label, name, type = "text", value, onChange }) {
  return <label className="field"><span>{label}</span><input name={name} type={type} value={value} onChange={onChange} /></label>;
}

function Textarea({ label, name, value, hint, onChange }) {
  return <label className="field field-wide"><span>{label}</span><textarea name={name} value={value} rows="5" placeholder="H-1001&#10;H-1002&#10;H-1003" onChange={onChange} />{hint && <small>{hint}</small>}</label>;
}

function Search({ value, setValue, count, placeholder = "Enter heat no" }) {
  return <div className="table-search"><label>Search by heat no</label><input type="search" value={value} placeholder={placeholder} onChange={e => setValue(e.target.value)} />{value && <button type="button" className="btn secondary compact" onClick={() => setValue("")}>Clear</button>}<span>{count} record(s)</span></div>;
}

function Stat({ label, value }) {
  return <div className="stat"><span>{label}</span><strong>{value ?? 0}</strong></div>;
}

function Stage({ label, value, tone }) {
  return <div className={`stage ${tone}`}><span>{label}</span><strong>{value ?? 0}</strong></div>;
}

function QueueCard({ title, value, detail }) {
  return <div className="queue-card"><span>{title}</span><strong>{value}</strong><p>{detail}</p></div>;
}

function filter(rows, search) {
  const query = search.trim().toLowerCase();
  if (!query) return rows;
  return rows.filter(row => heatValues(row).some(value => value.toLowerCase().includes(query)));
}

function heatValues(row) {
  const values = Array.isArray(row.heatNumbers) ? row.heatNumbers.filter(Boolean).map(String) : [];
  if (row.heatNo && !values.includes(row.heatNo)) values.unshift(String(row.heatNo));
  return values;
}

function workflowItemId(item) {
  return item.itemId || item.inventoryItemId || item.id;
}

function inWorkflow(item, tab) {
  if (tab === "process") return !item.processStatus || item.processStatus === "pending";
  if (tab === "machining") return item.processStatus === "ok" && (item.machiningStatus === "in_machining" || item.machiningStatus === "completed");
  if (tab === "ok") return item.inspectionStatus === "ok" || (item.inspectionStatus === "mixed" && Number(item.okItems || 0) > 0);
  return item.processStatus === "rejected" || item.inspectionStatus === "rejected" || (item.inspectionStatus === "mixed" && Number(item.notOkItems || 0) > 0);
}

function label(value) {
  return String(value).replace(/([A-Z])/g, " $1").replace(/^./, c => c.toUpperCase());
}

function currency(value) {
  const amount = Number(value || 0);
  return `Rs. ${amount.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
}

function processStatusLabel(status) {
  if (status === "ok") return "OK";
  if (status === "rejected") return "Rejected";
  return "Pending";
}

function appHelpAnswer(question, language = "en") {
  const text = question.toLowerCase();
  const dictionary = helpText[language] || helpText.en;
  const topics = [
    [["grn", "goods", "receipt", "inward"], "grn"],
    [["heat", "part"], "heat"],
    [["process", "quality", "reject"], "process"],
    [["machining", "machine work"], "machining"],
    [["cnc", "mtconnect", "agent"], "cnc"],
    [["invoice", "document", "file", "search"], "invoice"],
    [["purchase", "order", "po"], "po"],
    [["ai", "profit", "suggest", "prediction", "new order"], "ai"],
    [["user", "manager", "employee", "approve", "request"], "user"],
    [["salary", "wage", "employee rate"], "salary"]
  ];
  const match = topics.find(([words]) => words.some(word => text.includes(word)));
  return dictionary[match?.[1] || "fallback"];
}

function viewTitle(view) {
  return nav.find(([id]) => id === view)?.[1] || "Dashboard";
}

function arrivalFields() {
  return [["grnDate", "GRN date", "date"], ["grnTime", "GRN time", "time"], ["productDescription", "Description"], ["drawingNo", "Drawing no"], ["material", "Material"], ["hsCode", "HS code"], ["totalItems", "Quantity", "number"], ["ratePerItem", "Rate per piece", "number"], ["heatNumbers", "Heat no for each part", "textarea", "Enter one heat no per line. The number of lines must match the quantity."], ["customerName", "Customer name"], ["customerPhone", "Customer phone"]];
}

function poFields() {
  return [["drawingNo", "Drawing no"], ["companyName", "Company name"], ["productionRate", "Production rate", "number"], ["rateOnInward", "Rate on inward", "number"], ["finalRate", "Final rate", "number"]];
}

function salesFields() {
  return [["customerName", "Customer name"], ["customerPhone", "Customer phone"], ["drawingNo", "Drawing no"], ["description", "Item description"], ["quantity", "Quantity", "number"], ["rate", "Rate", "number"], ["dueDate", "Due date", "date"]];
}

function expenseFields() {
  return [["expenseDate", "Expense date", "date"], ["category", "Category"], ["description", "Description"], ["amount", "Amount", "number"], ["paidBy", "Paid by"]];
}

export default App;
