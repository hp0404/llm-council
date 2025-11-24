import { useState } from 'react';
import { auth } from '../api';
import './Login.css';

function Login({ onAuthenticated }) {
  const [token, setToken] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const isValid = await auth.verifyToken(token);
      if (isValid) {
        auth.setToken(token);
        onAuthenticated();
      } else {
        setError('Invalid token');
      }
    } catch (error) {
      setError('Invalid token. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-box">
        <h1>LLM Council</h1>
        <p className="login-description">
          Enter your authentication token to access the application
        </p>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <input
              type="password"
              placeholder="Authentication Token"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              disabled={isLoading}
              autoFocus
            />
          </div>
          {error && <div className="error-message">{error}</div>}
          <button type="submit" disabled={isLoading || !token}>
            {isLoading ? 'Verifying...' : 'Access'}
          </button>
        </form>
      </div>
    </div>
  );
}

export default Login;

