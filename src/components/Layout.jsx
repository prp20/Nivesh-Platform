import React from 'react';
import Navbar from './Navbar';
import BottomNavBar from './BottomNavBar';
import './Layout.css';

const Layout = ({ children }) => {
    return (
        <div className="layout">
            <Navbar />
            <main className="main-content">
                <div className="container">
                    {children}
                </div>
            </main>
            <BottomNavBar />
        </div>
    );
};

export default Layout;
