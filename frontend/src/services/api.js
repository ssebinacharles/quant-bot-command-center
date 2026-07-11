import axios from 'axios';

// This points directly to your active Django server
const API_BASE_URL = 'http://127.0.0.1:8000/api';

export const fetchTradeLogs = async () => {
    try {
        const response = await axios.get(`${API_BASE_URL}/trades/`);
        return response.data;
    } catch (error) {
        console.error("Error fetching trade logs. Is Django running?", error);
        return [];
    }
};