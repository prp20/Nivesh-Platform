import React from 'react';
import { useTheme } from '../context/ThemeContext';
import './Navbar.css';

const Navbar = () => {
    const { theme } = useTheme();

    return (
        <nav className="navbar">
            <div className="container navbar-content">
                <div className="logo font-heading">
                    <a href="#dashboard">NIVESH<span>ELITE</span></a>
                </div>

                <div className="nav-links">
                    <a href="#stocks" className="nav-link">STOCKS</a>
                    <a href="#mf" className="nav-link">FUNDS</a>
                    <a href="#indices" className="nav-link">INDICES</a>
                    <a href="#portfolio" className="nav-link">PORTFOLIO</a>
                </div>

                <div className="nav-actions">
                    <div className="search-bar">
                        <input type="text" placeholder="Search..." />
                    </div>
                    <div className="user-profile">
                        <div className="avatar"></div>
                    </div>
                </div>
            </div>
        </nav>
    );
};

export default Navbar;
