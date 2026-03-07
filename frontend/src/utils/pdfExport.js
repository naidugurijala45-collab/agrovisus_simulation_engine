import html2canvas from 'html2canvas';
import jsPDF from 'jspdf';

/**
 * Captures a React DOM element and exports it as a downloaded PDF file.
 * 
 * @param {HTMLElement} elementRef - The reference to the DOM element to capture.
 * @param {string} filename - The desired name of the downloaded file.
 */
export const exportElementToPDF = async (elementRef, filename = 'agrovisus-report.pdf') => {
    if (!elementRef) {
        console.error("No element provided for PDF export.");
        return false;
    }

    try {
        // 1. Capture the DOM element as a high-fidelity canvas
        const canvas = await html2canvas(elementRef, {
            scale: 2, // 2x scale for Retina/high-res crispness
            useCORS: true, // Allow external images/fonts if any
            backgroundColor: '#0a0f0d' // Match the dark theme background explicitly
        });

        // 2. Convert canvas to base64 image
        const imgData = canvas.toDataURL('image/jpeg', 0.95);

        // 3. Calculate PDF dimensions
        // A4 Paper: 210mm x 297mm
        const pdf = new jsPDF({
            orientation: 'portrait',
            unit: 'mm',
            format: 'a4'
        });

        const pdfWidth = pdf.internal.pageSize.getWidth();
        const pdfHeight = pdf.internal.pageSize.getHeight();

        // Calculate the height of the image on the PDF based on the aspect ratio
        const imgProps = pdf.getImageProperties(imgData);
        const imgHeight = (imgProps.height * pdfWidth) / imgProps.width;

        // 4. Handle multi-page pagination if the report is too long
        let heightLeft = imgHeight;
        let position = 0;

        // Add first page
        pdf.addImage(imgData, 'JPEG', 0, position, pdfWidth, imgHeight);
        heightLeft -= pdfHeight;

        // Add subsequent pages if the content bleeds over
        while (heightLeft >= 0) {
            position = heightLeft - imgHeight;
            pdf.addPage();
            pdf.addImage(imgData, 'JPEG', 0, position, pdfWidth, imgHeight);
            heightLeft -= pdfHeight;
        }

        // 5. Trigger download
        pdf.save(filename);
        return true;

    } catch (error) {
        console.error("Error generating PDF:", error);
        return false;
    }
};
