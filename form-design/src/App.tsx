import React from 'react'
import type { JSX } from 'react/jsx-runtime'

import Img from './components/Img.tsx'
import AverageRating from './components/AverageRating.tsx'
import RatingsHistogramRow from './components/RatingsHistogramRow.tsx'
import SnackBarContent from './components/SnackBarContent.tsx'
import GlobalNavigation from './components/GlobalNavigation.tsx'
import ReviewItem from './components/ReviewItem.tsx'
import GalleryCollectionRelatedBlock from './components/GalleryCollectionRelatedBlock.tsx'
import TemplateGalleryFooter from './components/TemplateGalleryFooter.tsx'
import SubNavigationHeader from './components/SubNavigationHeader.tsx'
import TemplateGalleryRow from './components/TemplateGalleryRow.tsx'
import Footer from './components/Footer.tsx'
import TemplateArticle from './components/TemplateArticle.tsx'
import GolfSessionForm from './components/GolfSessionForm.tsx'

import { BrowserRouter as Router, Routes, Route, useLocation, Navigate } from 'react-router-dom';

function AppContent() {
    const location = useLocation();

    return (
        <body>
        <div id={"__next"}>
        <div className={"base_theme__K5IIh black_palette_theme__nPj29 theme_theme__XHAvb"} style={{display:"contents"}}>
        <div className={"base_theme__FJXCL"} style={{display:"contents"}}>
        <div className={"globalNavigation_scrollSentinel__gP74N"}></div>
        <div className={"globalNavigation_globalNavigationWrapper__dUhMe globalNavigation_stickyWrapper__SYZfy"}>
        <div className={"base_theme__K5IIh black_palette_theme__nPj29 theme_theme__XHAvb"} style={{display:"contents"}}>
        <div className={"base_theme__FJXCL"} style={{display:"contents"}}>
        
                <GlobalNavigation />
            
        </div>
        </div>
        </div>
        
                <SubNavigationHeader
                    workLabel="Work"
                    schoolLabel="School"
                    lifeLabel="Life"
                />
            
        <main className={"layout_main__E4cY1"}>
        <div className={"Spacer_spacer__Hz1_q"} style={{minHeight:"24px"}}></div>
        
                <TemplateArticle title="Simple contact form" />
            
        <div className={"Spacer_spacer__Hz1_q"} style={{minHeight:"72px"}}></div>
        <div className={"TemplateRatingsAndReviews_container__eG9z4"}>
        <div className={"TemplateRatings_container__Fo9ig"}>
        <h3 className={"TemplateRatings_title__Dl0cN"}>
        Ratings & Reviews
        </h3>
        <div className={"TemplateRatings_metadata__shXkm"}>
        <div className={"TemplateRatings_averageContainer__9jw6S"}>
        
                <AverageRating average="5.0" max="5" />
            
        <span className={"typography_typography__Exx2D"} style={{"--typography-font":"var(--typography-sans-150-semibold-font)", "--typography-font-sm":"var(--typography-sans-150-semibold-font)", "--typography-letter-spacing":"var(--typography-sans-150-semibold-letter-spacing)", "--typography-letter-spacing-sm":"var(--typography-sans-150-semibold-letter-spacing)", "--typography-color":"inherit"}}>
        Based on 52 ratings
        </span>
        </div>
        <div className={"TemplateRatings_histogram__73mv1"}>
        
                    <RatingsHistogramRow rating={5} percentageLabel="96%" fillWidth="96.1538%" />
                
        
                    <RatingsHistogramRow rating={4} percentageLabel="4%" fillWidth="3.84615%" />
                
        
                    <RatingsHistogramRow rating={3} percentageLabel="0%" fillWidth="0%" />
                
        
                    <RatingsHistogramRow rating={2} percentageLabel="0%" fillWidth="0%" />
                
        
                    <RatingsHistogramRow rating={1} percentageLabel="0%" fillWidth="0%" />
                
        </div>
        </div>
        </div>
        <div className={"TemplateReviews_reviewsContainer__2CBGJ"}>
        <div role={"list"} className={"TemplateReviews_reviews__zSMgL"}>
        
                    <ReviewItem dataId="0" />
                
        
                    <ReviewItem dataId="1" />
                
        
                    <ReviewItem dataId="2" />
                
        </div>
        </div>
        </div>
        <div className={"Spacer_spacer__Hz1_q"} style={{minHeight:"120px"}}></div>
        
                    <TemplateGalleryRow dataId="0" />
                
        <div className={"Spacer_spacer__Hz1_q"} style={{minHeight:"10px"}}></div>
        
                    <TemplateGalleryRow dataId="1" />
                
        <div className={"Spacer_spacer__Hz1_q"} style={{minHeight:"10px"}}></div>
        <section className={"TemplateGalleryContentRow_contentRow__63ESj"}>
        <div className={"TemplateGalleryContentRow_header__F3cCg"}>
        <div className={"TemplateGalleryContentRow_heading__ofqyJ"}>
        <h3 id={":r8:"} className={"typography_typography__Exx2D heading_heading__OmVf6"} style={{"--typography-font":"var(--typography-sans-400-bold-font)", "--typography-font-sm":"var(--typography-sans-500-bold-font)", "--typography-letter-spacing":"var(--typography-sans-400-bold-letter-spacing)", "--typography-letter-spacing-sm":"var(--typography-sans-500-bold-letter-spacing)", "--typography-color":"inherit"}}>
        Featured in
        </h3>
        </div>
        </div>
        <div className={"grid_grid__caono"}>
        <div className={"gridItem_gridItem__aOo8I gridItem_span4__4hMOE"}>
        
                <GalleryCollectionRelatedBlock
                    title="Form-idable News"
                    subtitle="17 templates"
                    imageId="13"
                />
            
        </div>
        </div>
        </section>
        
                <TemplateGalleryFooter
                    imageId="14"
                    heading="Become a creator"
                    description="Submit your template to the Notion template gallery, get featured, and even get paid – all in just a few clicks."
                    buttonLabel="Get started"
                    buttonVariant="arrow"
                />
            
        </main>
        <div className={"snackBar_snackBar__IYfOp"}>
        <SnackBarContent />
        </div>
        <div className={"base_theme__K5IIh black_palette_theme__nPj29 theme_theme__XHAvb"} style={{display:"contents"}}>
        <div className={"base_theme__FJXCL"} style={{display:"contents"}}>
        <footer className={"footer_footerOuter__kubGm"}>
        <div className={"analyticsScrollPoint_analyticsScrollPoint__EZ4T_"}></div>
        
                <Footer year={2026} />
            
        </footer>
        </div>
        </div>
        </div>
        </div>
        </div>
        <iframe name={"__tcfapiLocator"} style={{display:"none"}}></iframe>
        <div id={"portal"}></div>
        <next-route-announcer>
        <p id={"__next-route-announcer__"} role={"alert"} style={{border:"0px", clip:"rect(0px,0px,0px,0px)", height:"1px", margin:"-1px", overflow:"hidden", padding:"0px", position:"absolute", top:"0px", width:"1px", whiteSpace:"nowrap", overflowWrap:"normal"}}></p>
        </next-route-announcer>
        <Img id="15" />
        <Img id="15" />
        <Img id="16" />
        <div id={"transcend-consent-manager"} style={{position:"fixed", zIndex:"2147483647"}}>
        <template shadowrootmode={"open"}>
        <div>
        <div></div>
        </div>
        </template>
        </div>
        </body>
    );
}

function GolfFormPage() {
    return (
        <body style={{ margin: 0, padding: 0 }}>
            <GolfSessionForm />
        </body>
    );
}

function App() {
    const defaultRoute = "/golf-form";

    return (
        <Router>
            <Routes>
                {defaultRoute !== '/' && <Route path="/" element={<Navigate to={defaultRoute} replace />} />}
                <Route path="/golf-form" element={<GolfFormPage />} />
                <Route path="/templates/*" element={<AppContent />} />
                <Route path="*" element={<GolfFormPage />} />
            </Routes>
        </Router>
    );
}

export default App
