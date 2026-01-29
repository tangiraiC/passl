import { useState, useEffect } from 'react'
import { Container, Row, Col, Card, Navbar, Nav, Table, Button, Badge, Form, Alert } from 'react-bootstrap';
import axios from 'axios';

// Configure Axios base URL
const api = axios.create({
  baseURL: 'http://localhost:8000/api/v1/'
});

function App() {
  const [user, setUser] = useState(null); // { username, password } for Basic Auth
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [stats, setStats] = useState({
    pendingOrders: 0,
    sales: 0,
    products: 0
  });

  const [orders, setOrders] = useState([]);

  // Login Form State
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  useEffect(() => {
    if (user) {
      fetchData();
    }
  }, [user]);

  const handleLogin = (e) => {
    e.preventDefault();
    // Simple Local determination of "Logged In" - real validation happens on data fetch
    setUser({ username, password });
  };

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const authHeader = 'Basic ' + btoa(user.username + ':' + user.password);
      const config = { headers: { 'Authorization': authHeader } };

      const [ordersRes, shopsRes] = await Promise.all([
        api.get('/orders/', config),
        api.get('/shops/', config)
      ]);

      setOrders(ordersRes.data);

      // Calculate Stats
      const pending = ordersRes.data.filter(o => o.status === 'CREATED').length;
      const totalSales = ordersRes.data.reduce((acc, o) => acc + parseFloat(o.total_amount), 0);

      setStats({
        pendingOrders: pending,
        sales: totalSales,
        products: shopsRes.data.reduce((acc, shop) => acc + (shop.products?.length || 0), 0)
      });

    } catch (err) {
      console.error(err);
      setError("Failed to fetch data. Check credentials or backend status.");
      setUser(null); // Logout on error
    } finally {
      setLoading(false);
    }
  };

  if (!user) {
    return (
      <Container className="d-flex align-items-center justify-content-center" style={{ minHeight: "100vh" }}>
        <Card style={{ width: '400px' }} className="shadow">
          <Card.Body>
            <h3 className="text-center mb-4">Shop Portal Login</h3>
            {error && <Alert variant="danger">{error}</Alert>}
            <Form onSubmit={handleLogin}>
              <Form.Group className="mb-3">
                <Form.Label>Username</Form.Label>
                <Form.Control type="text" value={username} onChange={e => setUsername(e.target.value)} required />
              </Form.Group>
              <Form.Group className="mb-3">
                <Form.Label>Password</Form.Label>
                <Form.Control type="password" value={password} onChange={e => setPassword(e.target.value)} required />
              </Form.Group>
              <div className="d-grid">
                <Button variant="primary" type="submit" disabled={loading}>
                  {loading ? 'Logging in...' : 'Login'}
                </Button>
                <div className="text-center mt-2">
                  <small className="text-muted">Use the credentials you created via Admin</small>
                </div>
              </div>
            </Form>
          </Card.Body>
        </Card>
      </Container>
    );
  }

  return (
    <>
      <Navbar bg="primary" variant="dark" expand="lg" className="mb-4">
        <Container>
          <Navbar.Brand href="#home">PASSL Shop Portal</Navbar.Brand>
          <Nav className="ms-auto">
            <Navbar.Text className="me-3 text-white">Signed in as: {user.username}</Navbar.Text>
            <Button variant="outline-light" size="sm" onClick={() => setUser(null)}>Logout</Button>
          </Nav>
        </Container>
      </Navbar>

      <Container>
        <h2 className="mb-4">Dashboard</h2>

        <Row className="mb-4">
          <Col md={4}>
            <Card bg="primary" text="white" className="mb-3">
              <Card.Body>
                <Card.Title>Pending Orders</Card.Title>
                <Card.Text className="display-4">{stats.pendingOrders}</Card.Text>
              </Card.Body>
            </Card>
          </Col>
          <Col md={4}>
            <Card bg="success" text="white" className="mb-3">
              <Card.Body>
                <Card.Title>Total Sales</Card.Title>
                <Card.Text className="display-4">${stats.sales.toFixed(2)}</Card.Text>
              </Card.Body>
            </Card>
          </Col>
          <Col md={4}>
            <Card bg="light" className="mb-3">
              <Card.Body>
                <Card.Title>Active Shops</Card.Title>
                <Card.Text className="display-4">{orders.length > 0 ? '1+' : '0'}</Card.Text>
              </Card.Body>
            </Card>
          </Col>
        </Row>

        <Card>
          <Card.Header className="bg-white d-flex justify-content-between align-items-center">
            <h5 className="mb-0">Recent Orders</h5>
            <Button size="sm" variant="outline-primary" onClick={fetchData}>Refresh</Button>
          </Card.Header>
          <div className="table-responsive">
            <Table hover className="mb-0">
              <thead>
                <tr>
                  <th>Order #</th>
                  <th>Customer</th>
                  <th>Items</th>
                  <th>Total</th>
                  <th>Status</th>
                  <th>Pmt Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {orders.length === 0 ? (
                  <tr><td colSpan="7" className="text-center py-4">No orders found.</td></tr>
                ) : orders.map(order => (
                  <tr key={order.id}>
                    <td>#{order.id}</td>
                    <td>Customer #{order.customer}</td>
                    <td>{order.items?.length || 0} items</td>
                    <td>${order.total_amount}</td>
                    <td>
                      <Badge bg={
                        order.status === 'CREATED' ? 'warning' :
                          order.status === 'DELIVERED' ? 'success' : 'primary'
                      } text="dark">
                        {order.status}
                      </Badge>
                    </td>
                    <td>
                      <Badge bg={order.payment_status === 'PAID' ? 'success' : 'secondary'}>{order.payment_status}</Badge>
                    </td>
                    <td>
                      <Button size="sm" variant="outline-primary">View</Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        </Card>
      </Container>
    </>
  )
}

export default App
