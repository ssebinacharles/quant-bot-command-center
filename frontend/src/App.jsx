import { useState, useEffect } from 'react';
import { fetchTradeLogs } from './services/api';
import { Activity, TrendingUp, TrendingDown } from 'lucide-react';

function App() {
  const [trades, setTrades] = useState([]);

  useEffect(() => {
    const loadData = async () => {
      const data = await fetchTradeLogs();
      setTrades(data);
    };
    
    // Fetch data immediately, then poll every 5 seconds for new Celery trades
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div style={{ padding: '40px', fontFamily: 'system-ui', maxWidth: '800px', margin: '0 auto' }}>
      <h1 style={{ display: 'flex', alignItems: 'center', gap: '10px', borderBottom: '2px solid #eee', paddingBottom: '10px' }}>
        <Activity color="#2563eb" /> AI Scalper Terminal
      </h1>
      
      <div style={{ marginTop: '20px' }}>
        <h3 style={{ color: '#4b5563' }}>Live Trade Logs ({trades.length} recorded)</h3>
        
        {trades.length === 0 ? (
          <div style={{ padding: '20px', backgroundColor: '#f3f4f6', borderRadius: '8px', textAlign: 'center' }}>
            <p>No trades found. Make sure your Django server and Celery tasks are running!</p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {trades.map((trade) => (
              <div key={trade.id} style={{ 
                padding: '16px', 
                border: '1px solid #e5e7eb',
                borderRadius: '8px',
                backgroundColor: trade.action === 'BUY' ? '#ecfdf5' : trade.action === 'SELL' ? '#fef2f2' : '#f9fafb',
                boxShadow: '0 1px 2px rgba(0,0,0,0.05)'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <strong style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '18px', color: trade.action === 'BUY' ? '#059669' : '#dc2626' }}>
                    {trade.action === 'BUY' ? <TrendingUp size={20} /> : <TrendingDown size={20} />}
                    {trade.action} XAUUSD
                  </strong>
                  <span style={{ fontSize: '14px', fontWeight: 'bold', color: '#374151', backgroundColor: '#e5e7eb', padding: '4px 8px', borderRadius: '4px' }}>
                    Confidence: {trade.ai_confidence_score}%
                  </span>
                </div>
                <p style={{ margin: 0, fontSize: '14px', color: '#4b5563', lineHeight: '1.5' }}>
                  <strong>AI Reasoning:</strong> {trade.raw_groq_response.reason}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;