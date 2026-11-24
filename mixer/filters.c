/* Transposed direct-form II cascade, with independent stereo state per band. */
__declspec(dllexport) void filter_stereo(const double *sos, double *state,
        const float *input, float *out, int frames, double gain) {
    for (int i=0;i<frames;i++) {
        double l=input[2*i], r=input[2*i+1];
        for (int k=0;k<6;k++) {
            const double *c=sos+6*k;
            double *s=state+4*k;
            double a=c[0]*l+s[0], b=c[0]*r+s[1];
            s[0]=c[1]*l-c[4]*a+s[2];
            s[1]=c[1]*r-c[4]*b+s[3];
            s[2]=c[2]*l-c[5]*a;
            s[3]=c[2]*r-c[5]*b;
            l=a; r=b;
        }
        out[2*i]=(float)(l*gain);
        out[2*i+1]=(float)(r*gain);
    }
}
